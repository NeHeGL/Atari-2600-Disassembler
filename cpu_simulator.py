"""
cpu_simulator.py - Minimal 6507 CPU execution tracer for Atari 2600 ROMs

Execution-traces a ROM up to MAX_INSTRUCTIONS, recording every PC visited.
Returns a Set[int] of ROM offsets actually executed.

Memory map:
  $0000-$007F  TIA registers (writes ignored, reads return 0)
  $0080-$01FF  RAM (128 bytes mirrored)
  $0200-$027F  TIA reads (return 0)
  $0280-$02FF  RIOT (return 0xFF for port reads)
  $1000-$1FFF  Current ROM bank (4K window)

Bank switching (triggered by any READ of the hotspot address):
  F8:  $1FF8/$1FF9          (2 banks x 4K =  8K)
  F6:  $1FF6-$1FF9          (4 banks x 4K = 16K)
  F4:  $1FF4-$1FFB          (8 banks x 4K = 32K)
  FA:  $1FF8-$1FFA          (3 banks x 4K = 12K)

Created by Jeff Molofee (NeHe) 2026
"""

from typing import Set, Dict, Optional
from core_opcodes import OPCODES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_INSTRUCTIONS       = 2_000_000   # Safety cap for normal mode
MAX_INSTRUCTIONS_DEEP  = 20_000_000  # Safety cap for deep/exhaustive mode
STACK_DEPTH_LIMIT      = 512         # Max JSR nesting (prevents infinite recursion)

# ---------------------------------------------------------------------------
# Bank-switching hotspot tables
# scheme -> {cpu_address: bank_index}
# ---------------------------------------------------------------------------

BANK_HOTSPOTS: Dict[str, Dict[int, int]] = {
    'F8': {0x1FF8: 0, 0x1FF9: 1},
    'F6': {0x1FF6: 0, 0x1FF7: 1, 0x1FF8: 2, 0x1FF9: 3},
    'F4': {0x1FF4: 0, 0x1FF5: 1, 0x1FF6: 2, 0x1FF7: 3,
           0x1FF8: 4, 0x1FF9: 5, 0x1FFA: 6, 0x1FFB: 7},
    'FA': {0x1FF8: 0, 0x1FF9: 1, 0x1FFA: 2},
}


def _detect_scheme(rom_size: int) -> Optional[str]:
    """Return the bank-switch scheme name for a given ROM size, or None."""
    return {8192: 'F8', 16384: 'F6', 32768: 'F4', 12288: 'FA'}.get(rom_size)


# ---------------------------------------------------------------------------
# CPU6507
# ---------------------------------------------------------------------------

class CPU6507:
    """
    Minimal 6507 CPU execution tracer.

    Does not aim for cycle-accuracy.  Its sole purpose is to faithfully
    follow all reachable code paths so that every instruction that could
    ever run on real hardware is recorded.

    Strategy
    --------
    * Single-step execution with a visited-PC set to avoid re-executing
      already-seen paths from the same (PC, bank) state.
    * Branches: execute the fall-through AND push the taken target onto a
      worklist so both paths are explored.
    * JSR: execute the subroutine inline (push return address on the
      Python stack); RTS pops it.  Infinite recursion is cut off by
      STACK_DEPTH_LIMIT.
    * JMP indirect: resolve the vector from memory and follow.
    * Bank switches: updating current_bank instantly, which is conservative
      but safe – it may visit the same ROM offset in multiple bank contexts.
    """

    def __init__(self, rom: bytearray, deep: bool = False) -> None:
        self.rom       = rom
        self.rom_size  = len(rom)
        self.scheme    = _detect_scheme(self.rom_size)
        self.bank_size = 4096
        self.num_banks = self.rom_size // self.bank_size if self.scheme else 1
        self._deep     = deep  # Enable exhaustive byte-by-byte entry point scan

        # Build the hotspot lookup for fast O(1) bank-switch detection
        self.hotspots: Dict[int, int] = {}  # cpu_addr -> bank_index
        if self.scheme and self.scheme in BANK_HOTSPOTS:
            self.hotspots = BANK_HOTSPOTS[self.scheme]

        # Visited (pc_in_bank_offset) states – avoids infinite loops
        # Key: (rom_offset_of_instruction, bank_index_at_that_time)
        self.visited: Set[tuple] = set()

        # Result: ROM offsets of instruction starts actually executed
        self.executed: Set[int] = set()

        # Dispatch table targets found by _scan_split_pointer_tables.
        # These are CPU addresses (not ROM offsets) of indirect-jump targets.
        # Exposed so callers can generate labels for them even though no
        # JSR or JMP absolute instruction directly references them.
        self.dispatch_targets: Set[int] = set()

        # CPU registers
        self.A:  int = 0
        self.X:  int = 0
        self.Y:  int = 0
        self.SP: int = 0xFF
        self.PC: int = 0          # 16-bit CPU address (not ROM offset)

        # Processor flags (each 0 or 1)
        self.N: int = 0  # Negative
        self.V: int = 0  # Overflow
        self.B: int = 0  # Break
        self.D: int = 0  # Decimal (ignored on 6507 but tracked)
        self.I: int = 1  # Interrupt disable
        self.Z: int = 0  # Zero
        self.C: int = 0  # Carry

        # RAM: $0080-$00FF (zero page), $0100-$01FF (stack)
        self.ram = bytearray(512)   # index 0 = $0000 ... 511 = $01FF

        # Current bank (index into ROM)
        self.current_bank: int = self.num_banks - 1  # Last bank always mapped at $F000

    # -----------------------------------------------------------------------
    # Memory access
    # -----------------------------------------------------------------------

    def _rom_offset(self, cpu_addr: int) -> int:
        """Convert a 13-bit CPU address (already masked) in $1000-$1FFF to a ROM file offset."""
        offset_in_bank = (cpu_addr & 0x1FFF) - 0x1000
        return self.current_bank * self.bank_size + offset_in_bank

    def mem_read(self, addr: int) -> int:
        """Read one byte from the 6507 address space (13-bit address bus)."""
        # 6507 has 13 address lines: mask to 13 bits so $F000 == $1000
        addr &= 0x1FFF

        # ROM window $1000-$1FFF (A12 = 1)
        if addr >= 0x1000:
            # Check for bank-switch hotspot BEFORE reading
            if addr in self.hotspots:
                self.current_bank = self.hotspots[addr]
            rom_off = self._rom_offset(addr)
            if 0 <= rom_off < self.rom_size:
                return self.rom[rom_off]
            return 0xFF

        # RAM: $0080-$01FF  (zero page $80-$FF + stack page $100-$1FF)
        if 0x0080 <= addr <= 0x01FF:
            return self.ram[addr - 0x0080]

        # TIA write-only area $0000-$007F – return 0 on read
        if addr <= 0x007F:
            return 0

        # TIA read registers $0200-$027F – return 0
        if 0x0200 <= addr <= 0x027F:
            return 0

        # RIOT $0280-$02FF – ports return 0xFF (all inputs pulled high)
        if 0x0280 <= addr <= 0x02FF:
            return 0xFF

        # Anything else (including mirrors): return 0
        return 0

    def mem_read_word(self, addr: int) -> int:
        """Read 16-bit little-endian word from address space."""
        lo = self.mem_read(addr)
        hi = self.mem_read((addr + 1) & 0xFFFF)
        return lo | (hi << 8)

    def mem_write(self, addr: int, value: int) -> None:
        """Write one byte; only RAM is mutable (TIA/RIOT writes are ignored)."""
        addr &= 0x1FFF  # 13-bit address bus
        value &= 0xFF
        if 0x0080 <= addr <= 0x01FF:
            self.ram[addr - 0x0080] = value
        # TIA / RIOT / ROM writes are silently ignored

    # -----------------------------------------------------------------------
    # Stack helpers
    # -----------------------------------------------------------------------

    def _push(self, value: int) -> None:
        self.mem_write(0x0100 | self.SP, value & 0xFF)
        self.SP = (self.SP - 1) & 0xFF

    def _pop(self) -> int:
        self.SP = (self.SP + 1) & 0xFF
        return self.mem_read(0x0100 | self.SP)

    def _push_word(self, value: int) -> None:
        self._push((value >> 8) & 0xFF)
        self._push(value & 0xFF)

    def _pop_word(self) -> int:
        lo = self._pop()
        hi = self._pop()
        return lo | (hi << 8)

    # -----------------------------------------------------------------------
    # Flag helpers
    # -----------------------------------------------------------------------

    def _set_nz(self, value: int) -> int:
        """Set N and Z flags based on value; return value & 0xFF."""
        value &= 0xFF
        self.N = 1 if (value & 0x80) else 0
        self.Z = 1 if value == 0 else 0
        return value

    def _flags_byte(self) -> int:
        return ((self.N << 7) | (self.V << 6) | (1 << 5) |
                (self.B << 4) | (self.D << 3) | (self.I << 2) |
                (self.Z << 1) | self.C)

    def _set_flags_byte(self, b: int) -> None:
        self.N = (b >> 7) & 1
        self.V = (b >> 6) & 1
        self.B = (b >> 4) & 1
        self.D = (b >> 3) & 1
        self.I = (b >> 2) & 1
        self.Z = (b >> 1) & 1
        self.C =  b       & 1

    # -----------------------------------------------------------------------
    # Addressing-mode effective address resolution
    # -----------------------------------------------------------------------

    def _ea(self, mode: str, pc_after_opcode: int) -> int:
        """
        Return the effective address for the given addressing mode.
        pc_after_opcode is the PC value just AFTER the opcode byte.
        """
        r = self.mem_read   # shorthand

        if mode == 'zeropage':
            return r(pc_after_opcode)
        if mode == 'zeropage_x':
            return (r(pc_after_opcode) + self.X) & 0xFF
        if mode == 'zeropage_y':
            return (r(pc_after_opcode) + self.Y) & 0xFF
        if mode == 'absolute':
            return r(pc_after_opcode) | (r(pc_after_opcode + 1) << 8)
        if mode == 'absolute_x':
            base = r(pc_after_opcode) | (r(pc_after_opcode + 1) << 8)
            return (base + self.X) & 0xFFFF
        if mode == 'absolute_y':
            base = r(pc_after_opcode) | (r(pc_after_opcode + 1) << 8)
            return (base + self.Y) & 0xFFFF
        if mode == 'indirect':
            ptr = r(pc_after_opcode) | (r(pc_after_opcode + 1) << 8)
            # 6502 page-wrap bug on indirect JMP
            ptr_hi = (ptr & 0xFF00) | ((ptr + 1) & 0xFF)
            return r(ptr) | (r(ptr_hi) << 8)
        if mode == 'indirect_x':
            zp = (r(pc_after_opcode) + self.X) & 0xFF
            return r(zp) | (r((zp + 1) & 0xFF) << 8)
        if mode == 'indirect_y':
            zp = r(pc_after_opcode)
            base = r(zp) | (r((zp + 1) & 0xFF) << 8)
            return (base + self.Y) & 0xFFFF
        # immediate / implied / accumulator / relative: not an effective address
        return 0


    # -----------------------------------------------------------------------
    # Single-step execution
    # -----------------------------------------------------------------------

    def step(self) -> bool:
        """Execute one instruction at PC. Returns True to keep going, False to stop."""
        pc = self.PC & 0xFFFF
        pc13 = pc & 0x1FFF  # 13-bit masked address
        if pc13 < 0x1000:
            return False  # not in ROM window
        opcode = self.mem_read(pc)  # mem_read applies 13-bit mask internally
        if opcode not in OPCODES:
            return False
        mnemonic, size, mode = OPCODES[opcode]
        rom_off = self._rom_offset(pc13)
        self.executed.add(rom_off)
        next_pc = (pc + size) & 0xFFFF
        self.PC = next_pc
        op1 = pc + 1

        # --- Load/Store ---
        if mnemonic == 'LDA':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            self.A = self._set_nz(v)
        elif mnemonic == 'LDX':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            self.X = self._set_nz(v)
        elif mnemonic == 'LDY':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            self.Y = self._set_nz(v)
        elif mnemonic == 'LAX':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            self.A = self.X = self._set_nz(v)
        elif mnemonic == 'STA':
            self.mem_write(self._ea(mode, op1), self.A)
        elif mnemonic == 'STX':
            self.mem_write(self._ea(mode, op1), self.X)
        elif mnemonic == 'STY':
            self.mem_write(self._ea(mode, op1), self.Y)
        elif mnemonic == 'SAX':
            self.mem_write(self._ea(mode, op1), self.A & self.X)

        # --- Transfers ---
        elif mnemonic == 'TAX': self.X = self._set_nz(self.A)
        elif mnemonic == 'TAY': self.Y = self._set_nz(self.A)
        elif mnemonic == 'TXA': self.A = self._set_nz(self.X)
        elif mnemonic == 'TYA': self.A = self._set_nz(self.Y)
        elif mnemonic == 'TXS': self.SP = self.X
        elif mnemonic == 'TSX': self.X = self._set_nz(self.SP)

        # --- Stack ---
        elif mnemonic == 'PHA': self._push(self.A)
        elif mnemonic == 'PHP': self._push(self._flags_byte() | 0x30)
        elif mnemonic == 'PLA': self.A = self._set_nz(self._pop())
        elif mnemonic == 'PLP': self._set_flags_byte(self._pop())

        # --- Flag operations ---
        elif mnemonic == 'CLC': self.C = 0
        elif mnemonic == 'SEC': self.C = 1
        elif mnemonic == 'CLI': self.I = 0
        elif mnemonic == 'SEI': self.I = 1
        elif mnemonic == 'CLV': self.V = 0
        elif mnemonic == 'CLD': self.D = 0
        elif mnemonic == 'SED': self.D = 1

        # --- Increment / Decrement ---
        elif mnemonic == 'INX': self.X = self._set_nz((self.X + 1) & 0xFF)
        elif mnemonic == 'DEX': self.X = self._set_nz((self.X - 1) & 0xFF)
        elif mnemonic == 'INY': self.Y = self._set_nz((self.Y + 1) & 0xFF)
        elif mnemonic == 'DEY': self.Y = self._set_nz((self.Y - 1) & 0xFF)
        elif mnemonic == 'INC':
            ea = self._ea(mode, op1)
            self.mem_write(ea, self._set_nz((self.mem_read(ea) + 1) & 0xFF))
        elif mnemonic == 'DEC':
            ea = self._ea(mode, op1)
            self.mem_write(ea, self._set_nz((self.mem_read(ea) - 1) & 0xFF))

        # --- Arithmetic ---
        elif mnemonic == 'ADC':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            result = self.A + v + self.C
            self.V = 1 if (~(self.A ^ v) & (self.A ^ result) & 0x80) else 0
            self.C = 1 if result > 0xFF else 0
            self.A = self._set_nz(result & 0xFF)
        elif mnemonic == 'SBC':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            result = self.A - v - (1 - self.C)
            self.V = 1 if ((self.A ^ v) & (self.A ^ result) & 0x80) else 0
            self.C = 0 if result < 0 else 1
            self.A = self._set_nz(result & 0xFF)
        elif mnemonic == 'CMP':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            result = self.A - v
            self.C = 0 if result < 0 else 1
            self._set_nz(result & 0xFF)
        elif mnemonic == 'CPX':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            result = self.X - v
            self.C = 0 if result < 0 else 1
            self._set_nz(result & 0xFF)
        elif mnemonic == 'CPY':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            result = self.Y - v
            self.C = 0 if result < 0 else 1
            self._set_nz(result & 0xFF)

        # --- Logic ---
        elif mnemonic == 'AND':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            self.A = self._set_nz(self.A & v)
        elif mnemonic == 'ORA':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            self.A = self._set_nz(self.A | v)
        elif mnemonic == 'EOR':
            v = self.mem_read(op1) if mode == 'immediate' else self.mem_read(self._ea(mode, op1))
            self.A = self._set_nz(self.A ^ v)
        elif mnemonic == 'BIT':
            v = self.mem_read(self._ea(mode, op1))
            self.Z = 1 if (self.A & v) == 0 else 0
            self.N = (v >> 7) & 1
            self.V = (v >> 6) & 1

        # --- Shift / Rotate ---
        elif mnemonic == 'ASL':
            if mode == 'accumulator':
                self.C = (self.A >> 7) & 1
                self.A = self._set_nz((self.A << 1) & 0xFF)
            else:
                ea = self._ea(mode, op1); v = self.mem_read(ea)
                self.C = (v >> 7) & 1
                self.mem_write(ea, self._set_nz((v << 1) & 0xFF))
        elif mnemonic == 'LSR':
            if mode == 'accumulator':
                self.C = self.A & 1
                self.A = self._set_nz(self.A >> 1)
            else:
                ea = self._ea(mode, op1); v = self.mem_read(ea)
                self.C = v & 1
                self.mem_write(ea, self._set_nz(v >> 1))
        elif mnemonic == 'ROL':
            if mode == 'accumulator':
                result = ((self.A << 1) | self.C) & 0xFF
                self.C = (self.A >> 7) & 1
                self.A = self._set_nz(result)
            else:
                ea = self._ea(mode, op1); v = self.mem_read(ea)
                result = ((v << 1) | self.C) & 0xFF
                self.C = (v >> 7) & 1
                self.mem_write(ea, self._set_nz(result))
        elif mnemonic == 'ROR':
            if mode == 'accumulator':
                result = ((self.C << 7) | (self.A >> 1)) & 0xFF
                self.C = self.A & 1
                self.A = self._set_nz(result)
            else:
                ea = self._ea(mode, op1); v = self.mem_read(ea)
                result = ((self.C << 7) | (v >> 1)) & 0xFF
                self.C = v & 1
                self.mem_write(ea, self._set_nz(result))

        # --- Illegal compound ops (approximate – flags only matter for tracing) ---
        elif mnemonic == 'SLO':  # ASL mem, then ORA
            ea = self._ea(mode, op1); v = self.mem_read(ea)
            self.C = (v >> 7) & 1; v2 = (v << 1) & 0xFF
            self.mem_write(ea, v2)
            self.A = self._set_nz(self.A | v2)
        elif mnemonic == 'RLA':  # ROL mem, then AND
            ea = self._ea(mode, op1); v = self.mem_read(ea)
            r2 = ((v << 1) | self.C) & 0xFF; self.C = (v >> 7) & 1
            self.mem_write(ea, r2)
            self.A = self._set_nz(self.A & r2)
        elif mnemonic == 'SRE':  # LSR mem, then EOR
            ea = self._ea(mode, op1); v = self.mem_read(ea)
            self.C = v & 1; v2 = v >> 1
            self.mem_write(ea, v2)
            self.A = self._set_nz(self.A ^ v2)
        elif mnemonic == 'RRA':  # ROR mem, then ADC
            ea = self._ea(mode, op1); v = self.mem_read(ea)
            r2 = ((self.C << 7) | (v >> 1)) & 0xFF; self.C = v & 1
            self.mem_write(ea, r2)
            result = self.A + r2 + self.C
            self.V = 1 if (~(self.A ^ r2) & (self.A ^ result) & 0x80) else 0
            self.C = 1 if result > 0xFF else 0
            self.A = self._set_nz(result & 0xFF)
        elif mnemonic == 'DCP':  # DEC mem, then CMP
            ea = self._ea(mode, op1); v = (self.mem_read(ea) - 1) & 0xFF
            self.mem_write(ea, v)
            r2 = self.A - v; self.C = 0 if r2 < 0 else 1; self._set_nz(r2 & 0xFF)
        elif mnemonic == 'ISC':  # INC mem, then SBC
            ea = self._ea(mode, op1); v = (self.mem_read(ea) + 1) & 0xFF
            self.mem_write(ea, v)
            result = self.A - v - (1 - self.C)
            self.V = 1 if ((self.A ^ v) & (self.A ^ result) & 0x80) else 0
            self.C = 0 if result < 0 else 1
            self.A = self._set_nz(result & 0xFF)
        elif mnemonic == 'ANC':
            v = self.mem_read(op1); self.A = self._set_nz(self.A & v); self.C = self.N
        elif mnemonic == 'ALR':
            v = self.mem_read(op1) & self.A; self.C = v & 1; self.A = self._set_nz(v >> 1)
        elif mnemonic == 'ARR':
            v = (self.mem_read(op1) & self.A)
            r2 = ((self.C << 7) | (v >> 1)) & 0xFF
            self.C = (r2 >> 6) & 1; self.V = ((r2 >> 6) ^ (r2 >> 5)) & 1
            self.A = self._set_nz(r2)
        elif mnemonic == 'AXS':
            v = self.mem_read(op1); r2 = (self.A & self.X) - v
            self.C = 0 if r2 < 0 else 1; self.X = self._set_nz(r2 & 0xFF)
        elif mnemonic in ('XAA','AHX','TAS','SHY','SHX','LAS','NOP'): pass  # ignore

        # --- Branches ---
        elif mnemonic in ('BPL','BMI','BVC','BVS','BCC','BCS','BNE','BEQ'):
            offset = self.mem_read(op1)
            if offset >= 128: offset -= 256
            taken = {
                'BPL': self.N == 0, 'BMI': self.N == 1,
                'BVC': self.V == 0, 'BVS': self.V == 1,
                'BCC': self.C == 0, 'BCS': self.C == 1,
                'BNE': self.Z == 0, 'BEQ': self.Z == 1,
            }[mnemonic]
            branch_target = (pc + 2 + offset) & 0xFFFF
            if taken:
                self.PC = branch_target
            # Always push the NOT-taken path onto worklist for full coverage
            not_taken_pc = next_pc if taken else branch_target
            self._worklist.append((not_taken_pc, self.current_bank))

        # --- Jumps ---
        elif mnemonic == 'JMP':
            target = self._ea(mode, op1)
            self.PC = target
            return True   # caller loop will continue from new PC

        # --- JSR ---
        elif mnemonic == 'JSR':
            target = self.mem_read(op1) | (self.mem_read(op1 + 1) << 8)
            ret_addr = (next_pc - 1) & 0xFFFF   # 6502 pushes PC-1
            self._push((ret_addr >> 8) & 0xFF)
            self._push(ret_addr & 0xFF)
            self.PC = target
            return True

        # --- RTS ---
        elif mnemonic == 'RTS':
            lo = self._pop(); hi = self._pop()
            self.PC = ((lo | (hi << 8)) + 1) & 0xFFFF
            return True

        # --- RTI ---
        elif mnemonic == 'RTI':
            self._set_flags_byte(self._pop())
            lo = self._pop(); hi = self._pop()
            self.PC = lo | (hi << 8)
            return True

        # --- BRK ---
        elif mnemonic == 'BRK':
            return False   # treat as halt for tracing purposes

        return True

    # -----------------------------------------------------------------------
    # Main execution loop
    # -----------------------------------------------------------------------

    def _seed_vectors(self, bank_idx: int) -> list:
        """
        Read NMI/RESET/IRQ vectors from a bank and return valid (cpu_pc, bank_idx) seeds.
        Vectors live at the last 6 bytes of the 4K bank window ($FFFA-$FFFF).
        """
        seeds = []
        bank_start = bank_idx * self.bank_size
        # Vector offsets within the bank: $FFFA=offset $FFA, $FFFC=offset $FFC, $FFFE=offset $FFE
        for vec_off in (0xFFA, 0xFFC, 0xFFE):
            if bank_start + vec_off + 1 < self.rom_size:
                lo = self.rom[bank_start + vec_off]
                hi = self.rom[bank_start + vec_off + 1]
                vec = lo | (hi << 8)
                vec13 = vec & 0x1FFF
                if vec13 >= 0x1000:  # points into ROM window
                    seeds.append((vec, bank_idx))
        return seeds

    def _scan_embedded_refs(self) -> list:
        """
        Scan the entire ROM for embedded JSR $addr and JMP $addr patterns.
        Every absolute address that points into ROM becomes a worklist seed.
        This catches code sections that are only reachable via RAM-computed
        pointers or conditional branches that depend on runtime register state.
        Returns list of (cpu_pc, bank_idx) tuples.
        """
        seeds = []
        rom = self.rom
        rom_size = self.rom_size
        bank_size = self.bank_size

        for bank_idx in range(self.num_banks):
            bank_start = bank_idx * bank_size
            bank_end   = min(bank_start + bank_size, rom_size)
            for i in range(bank_start, bank_end - 2):
                b = rom[i]
                # JSR $addr (opcode $20) or JMP $addr absolute (opcode $4C)
                if b == 0x20 or b == 0x4C:
                    lo = rom[i + 1]
                    hi = rom[i + 2]
                    addr = lo | (hi << 8)
                    addr13 = addr & 0x1FFF
                    if addr13 >= 0x1000:
                        # Determine which bank this cpu address lives in.
                        # For single-bank ROMs it's always bank 0.
                        # For multi-bank ROMs we don't know at scan time,
                        # so seed with every bank (the visited set dedupes).
                        if self.num_banks == 1:
                            seeds.append((addr, 0))
                        else:
                            for b2 in range(self.num_banks):
                                seeds.append((addr, b2))
        return seeds

    def _scan_word_table_refs(self) -> list:
        """
        Scan each bank for 16-bit word pairs that look like ROM pointers.
        Many Atari 2600 games store dispatch tables of code addresses in ROM:
          .word SubA, SubB, SubC   ; jump table indexed by X or Y
        These appear as pairs of bytes where both bytes form an address in
        $F000-$FFFF (i.e. 13-bit masked to $1000-$1FFF).
        We scan every even and odd aligned word in each bank.
        Returns list of (cpu_pc, bank_idx) tuples.
        """
        seeds = []
        rom = self.rom
        rom_size = self.rom_size
        bank_size = self.bank_size

        for bank_idx in range(self.num_banks):
            bank_start = bank_idx * bank_size
            bank_end   = min(bank_start + bank_size, rom_size)
            for i in range(bank_start, bank_end - 1):
                lo = rom[i]
                hi = rom[i + 1]
                addr = lo | (hi << 8)
                addr13 = addr & 0x1FFF
                # Must point into ROM window AND hi byte must be $F0-$FF
                # (common for Atari 2600 ROM addresses)
                if addr13 >= 0x1000 and (hi & 0xF0) == 0xF0:
                    if self.num_banks == 1:
                        seeds.append((addr, 0))
                    else:
                        for b2 in range(self.num_banks):
                            seeds.append((addr, b2))
        return seeds

    def _resolve_indirect_jmp_via_tables(self, jmp_rom_off: int, bank_idx: int) -> list:
        """
        Given the ROM offset of a JMP ($zp) instruction, scan backwards in ROM
        to find the split lo/hi pointer table pattern:

          LDA lo_table,Y   ($B9 lo hi)   – load lo byte of target
          STA $zp          ($85 zp)
          LDA hi_table,Y   ($B9 lo hi)   – load hi byte of target
          STA $zp+1        ($85 zp+1)
          JMP ($zp)        ($6C zp 00)

        If found, walk both tables for every Y value (0, 1, 2, ...) until the
        hi byte is no longer a valid ROM page, and return all targets as seeds.
        Also records each target in self.dispatch_targets.

        This is the *dynamic* counterpart to _scan_split_pointer_tables:
        called at runtime when the executor actually reaches a JMP ($zp).

        Returns list of (cpu_pc, bank_idx) tuples.
        """
        rom      = self.rom
        rom_size = self.rom_size
        bank_size = self.bank_size
        bank_start = bank_idx * bank_size
        bank_end   = min(bank_start + bank_size, rom_size)

        zp = rom[jmp_rom_off + 1]   # zero-page address of pointer lo

        lo_table_addr = None
        hi_table_addr = None

        scan_start = max(bank_start, jmp_rom_off - 40)
        i = scan_start
        while i < jmp_rom_off:
            op = rom[i]
            if op == 0x85 and i + 1 < jmp_rom_off:   # STA zp
                dest_zp = rom[i + 1]
                if dest_zp == zp:
                    for k in range(max(scan_start, i - 6), i):
                        if rom[k] in (0xB9, 0xBD) and k + 2 < i:
                            ref = rom[k + 1] | (rom[k + 2] << 8)
                            if (ref & 0x1FFF) >= 0x1000:
                                lo_table_addr = ref
                elif dest_zp == (zp + 1) & 0xFF:
                    for k in range(max(scan_start, i - 6), i):
                        if rom[k] in (0xB9, 0xBD) and k + 2 < i:
                            ref = rom[k + 1] | (rom[k + 2] << 8)
                            if (ref & 0x1FFF) >= 0x1000:
                                hi_table_addr = ref
                i += 2
            else:
                i += 1

        if lo_table_addr is None or hi_table_addr is None:
            return []

        lo_rom_off = lo_table_addr - 0xF000 + bank_idx * bank_size
        hi_rom_off = hi_table_addr - 0xF000 + bank_idx * bank_size

        if not (0 <= lo_rom_off < rom_size and 0 <= hi_rom_off < rom_size):
            return []

        seeds = []
        consecutive_invalid = 0
        for entry in range(64):   # safety limit
            lo_off = lo_rom_off + entry
            hi_off = hi_rom_off + entry
            if lo_off >= rom_size or hi_off >= rom_size:
                break
            lo_byte = rom[lo_off]
            hi_byte = rom[hi_off]
            target_addr = (hi_byte << 8) | lo_byte
            # Valid Atari 2600 ROM addresses have hi byte in $E0-$FF range
            # and must point into the ROM window.
            # Some dispatch tables use Y=0 as a dummy/sentinel entry (e.g. an
            # RTS stub at a non-ROM address) so the first entry's hi byte may
            # be invalid.  Allow up to 2 consecutive invalid entries before
            # giving up, to handle tables that are 1-indexed or have a leading
            # dummy entry.
            is_valid = ((hi_byte & 0xE0) == 0xE0) and ((target_addr & 0x1FFF) >= 0x1000)
            if not is_valid:
                consecutive_invalid += 1
                if consecutive_invalid > 2:
                    break
                continue
            consecutive_invalid = 0
            self.dispatch_targets.add(target_addr)
            if self.num_banks == 1:
                seeds.append((target_addr, 0))
            else:
                for b2 in range(self.num_banks):
                    seeds.append((target_addr, b2))
        return seeds

    def _scan_split_pointer_tables(self) -> list:
        """
        Scan ROM for the split lo/hi pointer table dispatch pattern:

          LDA lo_table,Y   ($B9 lo hi)   – load lo byte of target into A
          STA $zp          ($85 zp)       – store into zero-page pointer lo
          LDA hi_table,Y   ($B9 lo hi)   – load hi byte into A
          STA $zp+1        ($85 zp+1)    – store into zero-page pointer hi
          JMP ($zp)        ($6C zp 00)   – indirect jump through pointer

        When found, we reconstruct every entry in both tables and seed all
        addresses that look like valid ROM pointers as code entry points.

        We also handle the X-indexed variant (LDA abs,X / $BD) and the
        case where hi is loaded first.

        NOTE: This is the *static* pre-scan version run before execution starts.
        The dynamic version (_resolve_indirect_jmp_via_tables) is called at
        runtime whenever the executor actually hits a JMP ($zp) instruction.
        Both are kept for maximum coverage: static catches tables in banks that
        might not be reached by the main execution path; dynamic catches tables
        that the static scan might miss due to its fixed backward-scan window.

        Returns list of (cpu_pc, bank_idx) tuples.
        """
        seeds = []
        rom      = self.rom
        rom_size = self.rom_size
        bank_size = self.bank_size

        # For each bank, scan for JMP ($zp) = 0x6C followed by a zero-page address
        for bank_idx in range(self.num_banks):
            bank_start = bank_idx * bank_size
            bank_end   = min(bank_start + bank_size, rom_size)

            for jmp_off in range(bank_start, bank_end - 2):
                if rom[jmp_off] != 0x6C:  # JMP indirect
                    continue
                zp = rom[jmp_off + 1]     # zero-page address of pointer lo
                if rom[jmp_off + 2] != 0x00:
                    continue              # must be zero-page form $6C zp 00

                # Scan backwards (up to 40 bytes) for the STA $zp and STA $zp+1
                # that set up this pointer, and find the LDA abs,Y that loads them.
                lo_table_addr = None
                hi_table_addr = None

                scan_start = max(bank_start, jmp_off - 40)
                # Collect all STA zp instructions in the window
                i = scan_start
                while i < jmp_off:
                    op = rom[i]
                    if op == 0x85 and i + 1 < jmp_off:   # STA zp
                        dest_zp = rom[i + 1]
                        if dest_zp == zp:
                            # This stores the lo byte – look back for LDA abs,Y or LDA abs,X
                            for k in range(max(scan_start, i - 6), i):
                                if rom[k] in (0xB9, 0xBD) and k + 2 < i:  # LDA abs,Y / LDA abs,X
                                    ref = rom[k + 1] | (rom[k + 2] << 8)
                                    ref13 = ref & 0x1FFF
                                    if ref13 >= 0x1000:
                                        lo_table_addr = ref
                        elif dest_zp == (zp + 1) & 0xFF:
                            # This stores the hi byte
                            for k in range(max(scan_start, i - 6), i):
                                if rom[k] in (0xB9, 0xBD) and k + 2 < i:
                                    ref = rom[k + 1] | (rom[k + 2] << 8)
                                    ref13 = ref & 0x1FFF
                                    if ref13 >= 0x1000:
                                        hi_table_addr = ref
                        i += 2
                    else:
                        i += 1

                if lo_table_addr is None or hi_table_addr is None:
                    continue

                # We found a dispatch table pair.  Extract addresses by walking
                # both tables simultaneously until we hit non-ROM hi bytes.
                lo_rom_off = lo_table_addr - 0xF000 + bank_idx * bank_size
                hi_rom_off = hi_table_addr - 0xF000 + bank_idx * bank_size

                # Clamp to valid ROM range
                if not (0 <= lo_rom_off < rom_size and 0 <= hi_rom_off < rom_size):
                    continue

                # Read table entries until hi byte is not a valid ROM page ($F0-$FF)
                max_entries = 64  # safety limit
                for entry in range(max_entries):
                    lo_off = lo_rom_off + entry
                    hi_off = hi_rom_off + entry
                    if lo_off >= rom_size or hi_off >= rom_size:
                        break
                    lo_byte = rom[lo_off]
                    hi_byte = rom[hi_off]
                    # Valid Atari 2600 ROM addresses have hi byte $F0-$FF
                    # (or $C0-$FF for large banked ROMs)
                    if (hi_byte & 0xE0) != 0xE0:
                        break
                    target_addr = (hi_byte << 8) | lo_byte
                    target13    = target_addr & 0x1FFF
                    if target13 < 0x1000:
                        break
                    # Record as a dispatch target (for label generation)
                    self.dispatch_targets.add(target_addr)
                    # Seed as entry point in the appropriate bank
                    if self.num_banks == 1:
                        seeds.append((target_addr, 0))
                    else:
                        for b2 in range(self.num_banks):
                            seeds.append((target_addr, b2))

        return seeds

    def run(self) -> 'Set[int]':
        """
        Trace execution starting from the RESET vector.

        Uses recursive-descent worklist exploration:
        - Both branch paths (taken + not-taken) are always added to the worklist
        - Visited set is per rom_offset (not per register state)
        - JMP/JSR targets are added to worklist; execution continues past JSR
        - RTS/RTI/BRK end the current linear path
        - Bank switches add the new bank context to the worklist

        After the primary worklist empties, a second pass seeds from:
        1. NMI/RESET/IRQ vectors in ALL banks
        2. Every JSR/JMP absolute target found anywhere in ROM

        Returns set of ROM offsets (instruction starts) actually executed.
        """
        rom_size = self.rom_size

        # --- Phase 1: seed from all banks' interrupt vectors ---
        self._worklist = []
        for bank_idx in range(self.num_banks):
            self._worklist.extend(self._seed_vectors(bank_idx))

        # Fallback: if no valid vectors found, try the canonical RESET location
        if not self._worklist:
            reset_lo = self.rom[rom_size - 4]
            reset_hi = self.rom[rom_size - 3]
            reset_vec = reset_lo | (reset_hi << 8)
            self._worklist = [(reset_vec, self.num_banks - 1)]

        # --- Phase 2: seed from every JSR/JMP absolute target in ROM ---
        # IMPORTANT: We only include JSR/JMP instructions that are themselves
        # already in self.executed (confirmed code from Phase 1).  Scanning raw
        # ROM bytes naively finds JSR/JMP opcodes inside sprite data and data
        # tables, seeding their "targets" as code entry points even though the
        # CPU never actually executes those bytes.
        #
        # Strategy: run Phase 1 worklist first, then filter.
        # We'll extend the worklist a second time after Phase 1 completes.
        # (The _scan_embedded_refs_from_executed() call happens below, after the
        #  initial worklist drains.)

        # --- Phase 3: seed from split lo/hi pointer dispatch tables ---
        # Many Atari 2600 games use indirect jumps via a RAM pointer loaded from
        # two parallel ROM tables:
        #   LDA lo_table,Y / STA $zp     (load lo byte of target)
        #   LDA hi_table,Y / STA $zp+1   (load hi byte of target)
        #   JMP ($zp)                     (indirect jump through RAM pointer)
        # We detect this pattern and extract all addresses from the lo/hi tables.
        # This is SAFE (not speculative) because we only add entries from tables
        # that we can prove are actually used as dispatch tables in the code.
        self._worklist.extend(self._scan_split_pointer_tables())

        # NOTE: The old Phases 3 (word-table scan), 4 (post-RTS seeding), and 5
        # (deep byte-by-byte scan) have been intentionally removed.  Those phases
        # seeded speculative entry points by scanning raw ROM bytes without regard
        # for whether the CPU could actually reach them, causing sprite bitmaps and
        # lookup tables to be misclassified as code.

        # Visited: set of (rom_offset, bank) to avoid infinite loops
        visited: 'Set[tuple]' = set()

        instruction_count = 0
        max_insns = MAX_INSTRUCTIONS_DEEP if self._deep else MAX_INSTRUCTIONS

        # Run Phase 1 + Phase 3 first
        while self._worklist and instruction_count < max_insns:
            start_pc, start_bank = self._worklist.pop()
            self.current_bank = start_bank
            self.PC = start_pc

            while instruction_count < max_insns:
                pc = self.PC & 0xFFFF
                pc13 = pc & 0x1FFF
                if pc13 < 0x1000:
                    break
                rom_off = self._rom_offset(pc13)
                if rom_off >= rom_size:
                    break
                opcode = self.rom[rom_off]
                # Special case: BRK ($00) must be added to executed even if this
                # (rom_off, bank) state was already visited via a different path.
                # Without this, a BRK reached by two different branches gets added
                # to 'visited' on the first visit but not to 'executed', so Phase 2.5
                # never sees it and fails to seed the code immediately following it.
                if opcode == 0x00:
                    if not (rom_off + 3 < rom_size and
                            self.rom[rom_off + 1] == 0x00 and
                            self.rom[rom_off + 2] == 0x00 and
                            self.rom[rom_off + 3] == 0x00):
                        self.executed.add(rom_off)  # Record BRK regardless of visited state
                    break  # Always stop linear path at BRK (whether ROM fill or not)
                state = (rom_off, self.current_bank)
                if state in visited:
                    break
                visited.add(state)
                if opcode not in OPCODES:
                    break
                if opcode == 0xFF:
                    # Check if this looks like ROM fill: 3 more $FF bytes after opcode
                    if (rom_off + 3 < rom_size and
                            self.rom[rom_off + 1] == 0xFF and
                            self.rom[rom_off + 2] == 0xFF and
                            self.rom[rom_off + 3] == 0xFF):
                        break  # Four consecutive $FF = ROM fill, not valid ISC opcode
                mnemonic, size, mode = OPCODES[opcode]
                self.executed.add(rom_off)
                instruction_count += 1
                next_pc = (pc + size) & 0xFFFF
                op1 = pc + 1
                if mnemonic in ('BPL','BMI','BVC','BVS','BCC','BCS','BNE','BEQ'):
                    offset = self.mem_read(op1)
                    if offset >= 128: offset -= 256
                    branch_target = (pc + 2 + offset) & 0xFFFF
                    self._worklist.append((next_pc, self.current_bank))
                    self._worklist.append((branch_target, self.current_bank))
                    break
                elif mnemonic == 'JMP' and mode == 'absolute':
                    target = self.mem_read(op1) | (self.mem_read(op1 + 1) << 8)
                    self._worklist.append((target, self.current_bank))
                    break
                elif mnemonic == 'JMP' and mode == 'indirect':
                    # Resolve the JMP ($zp) or JMP ($addr) target.
                    # The pointer address is read from the opcode's operand bytes.
                    # For zero-page pointers ($zp, $zp+1) the value is in RAM which
                    # the simulator has been maintaining via LDA/STA instructions.
                    # For ROM-based vector tables (ptr >= $1000) read from ROM directly.
                    ptr = self.mem_read(op1) | (self.mem_read(op1 + 1) << 8)
                    ptr13 = ptr & 0x1FFF
                    if ptr13 >= 0x1000:
                        # Pointer is in ROM — read the target from ROM
                        ptr_off = self._rom_offset(ptr13)
                        if ptr_off + 1 < rom_size:
                            lo = self.rom[ptr_off]
                            hi = self.rom[ptr_off + 1]
                            target = lo | (hi << 8)
                            self._worklist.append((target, self.current_bank))
                    else:
                        # Pointer is in RAM/zero-page — read target from mem_read
                        # which correctly returns the RAM value built up by previous
                        # LDA #imm / STA $zp instructions in the current path.
                        lo = self.mem_read(ptr)
                        hi = self.mem_read((ptr + 1) & 0xFFFF)
                        target = lo | (hi << 8)
                        target13 = target & 0x1FFF
                        if target13 >= 0x1000:
                            # Valid ROM target — seed the specific computed address
                            self._worklist.append((target, self.current_bank))
                        # The hi byte of a RAM pointer is typically set ONCE (to a ROM page
                        # like $F0) and the lo byte varies at runtime (different kernel
                        # variants, scanline counters, etc.).  We cannot know all runtime
                        # lo values from a single trace, so we enumerate candidate lo values
                        # for this hi page and seed those that look like valid code entry points.
                        # IMPORTANT: We require at least 3 consecutive valid instructions
                        # starting at the probe address to reduce false positives from
                        # sprite/data bytes that happen to be valid opcodes.
                        # We only do this when hi is in the ROM page range ($E0-$FF).
                        if (hi & 0xE0) == 0xE0:
                            hi_page = hi << 8
                            for lo_probe in range(256):
                                if lo_probe == lo:
                                    continue  # already seeded the specific value
                                probe = (hi_page | lo_probe) & 0x1FFF
                                if probe < 0x1000:
                                    continue
                                probe_rom_off = self._rom_offset(probe)
                                if probe_rom_off < 0 or probe_rom_off >= rom_size:
                                    continue
                                # Require 3 consecutive valid instructions at this address
                                # before seeding it — strong enough to reject sprite data
                                # (which has random byte patterns) but allow real code
                                # entry points (which always start with a valid instruction
                                # followed by valid operand bytes).
                                p = probe_rom_off
                                valid_seq = 0
                                for _ in range(3):
                                    if p >= rom_size:
                                        break
                                    b = self.rom[p]
                                    if b not in OPCODES or b == 0x00:
                                        break
                                    _, bsz, _ = OPCODES[b]
                                    p += bsz
                                    valid_seq += 1
                                if valid_seq >= 3:
                                    self._worklist.append((hi_page | lo_probe, self.current_bank))
                    # Dynamic dispatch table resolution: scan backwards in ROM
                    # for the LDA abs,Y/STA $zp pattern and walk all table entries.
                    # This discovers all Y-indexed dispatch targets dynamically.
                    dyn_seeds = self._resolve_indirect_jmp_via_tables(rom_off, self.current_bank)
                    self._worklist.extend(dyn_seeds)
                    break
                elif mnemonic == 'JSR':
                    target = self.mem_read(op1) | (self.mem_read(op1 + 1) << 8)
                    self._worklist.append((target, self.current_bank))
                    self.PC = next_pc
                    continue
                elif mnemonic in ('RTS', 'RTI', 'BRK'):
                    break
                else:
                    prev_bank = self.current_bank
                    self.PC = next_pc
                    self._execute_noncf(mnemonic, mode, op1)
                    if self.current_bank != prev_bank:
                        self._worklist.append((self.PC, self.current_bank))
                        break
                    continue

        # --- Phase 2: seed from JSR/JMP targets that are in CONFIRMED CODE ---
        # Now that Phase 1 has run, self.executed contains every ROM offset we
        # know is real code.  Scan those offsets for JSR/JMP absolute instructions
        # and add their targets to the worklist.  This is safe because we only
        # look at instructions we already confirmed as code — sprite data bytes
        # are excluded because they are NOT in self.executed.
        #
        # IMPORTANT for banked ROMs: A JMP/JSR at ROM offset X is in bank X//4096.
        # We seed the target with ONLY that same bank, not all banks.  Seeding all
        # banks is wrong because the same CPU address maps to completely different
        # ROM data in different banks — and the jump only makes sense in the context
        # of the bank where the instruction lives.
        # Exception: the last bank (always mapped) seeds into itself regardless.
        _phase2_seeds = []
        for _rom_off in sorted(self.executed):
            _op = self.rom[_rom_off]
            if _op not in (0x20, 0x4C):  # JSR or JMP absolute
                continue
            if _rom_off + 2 >= rom_size:
                continue
            _lo = self.rom[_rom_off + 1]
            _hi = self.rom[_rom_off + 2]
            _addr = _lo | (_hi << 8)
            _addr13 = _addr & 0x1FFF
            if _addr13 < 0x1000:
                continue
            if self.num_banks == 1:
                _phase2_seeds.append((_addr, 0))
            else:
                # For banked ROMs, seed the target in each bank where the ROM
                # bytes at that offset look like valid code (>= 3 consecutive
                # valid instructions starting there).  This allows cross-bank
                # dispatch (where a jump target makes sense in multiple banks)
                # while rejecting banks where the same offset contains data.
                _addr_offset_in_bank = _addr_offset_in_bank = _addr13 - 0x1000  # offset within 4K bank
                for _b2 in range(self.num_banks):
                    _candidate_rom_off = _b2 * self.bank_size + _addr_offset_in_bank
                    if _candidate_rom_off < 0 or _candidate_rom_off + 2 >= rom_size:
                        continue
                    # Require 3 consecutive valid instructions (no $00/BRK)
                    _p = _candidate_rom_off
                    _vseq = 0
                    for _ in range(3):
                        if _p >= rom_size:
                            break
                        _b3 = self.rom[_p]
                        if _b3 not in OPCODES or _b3 == 0x00:
                            break
                        _, _bsz, _ = OPCODES[_b3]
                        _p += _bsz
                        _vseq += 1
                    if _vseq >= 3:
                        _phase2_seeds.append((_addr, _b2))
        self._worklist.extend(_phase2_seeds)

        # --- Phase 2.5: seed bytes immediately after RTS/RTI/JMP in confirmed code ---
        # Many Atari 2600 ROMs place valid code immediately after a terminal instruction
        # (RTS, RTI, or JMP) that the CPU never falls through to.  These bytes are still
        # real code — they may be subroutine stubs entered via JSR from elsewhere in the
        # ROM, or dead code that was once called but the call site was removed.
        #
        # We detect this by looking at every RTS/RTI/JMP instruction in confirmed code
        # and checking whether the byte immediately following it starts a long run of
        # valid instructions (>= 10 consecutive valid non-BRK instructions).
        # If so, we seed that address as a new entry point.
        #
        # Using JMP (in addition to RTS/RTI) catches the common pattern where:
        #   JMP somewhere          ; confirmed code, unconditional
        #   <unreachable stub>     ; subroutine stub right after the JMP
        #   RTS                    ; stub ends here
        #
        # This is conservative: we require 10+ valid instructions to avoid seeding
        # data blocks that happen to start with a few valid-looking opcode bytes.
        _post_terminal_seeds = []
        for _rom_off in sorted(self.executed):
            _op = self.rom[_rom_off]
            if _op not in OPCODES:
                continue
            _mn, _sz, _md = OPCODES[_op]
            # Terminal instructions: RTS (1 byte), RTI (1 byte), JMP absolute (3 bytes),
            # BRK (1 byte — stops linear path, but following bytes may be real code)
            is_terminal = (
                _mn in ('RTS', 'RTI', 'BRK') or
                (_mn == 'JMP' and _md == 'absolute' and _sz == 3)
            )
            if not is_terminal:
                continue
            # Check the byte immediately after this terminal instruction
            _next_off = _rom_off + _sz
            if _next_off >= rom_size:
                continue
            if _next_off in self.executed:
                continue  # already traced
            # Count consecutive valid instructions starting here, allowing BRK
            # to appear within the sequence (BRK is a valid instruction in code).
            # For RTS/RTI/JMP: require 10+ non-BRK instructions (strict).
            # For BRK: require 5+ instructions (looser — code after BRK is
            # commonly a dead code stub that may contain BRK markers itself).
            _threshold = 5 if _mn == 'BRK' else 10
            _p = _next_off
            _vseq = 0
            _brkseq = 0
            for _ in range(max(10, _threshold + 2)):
                if _p >= rom_size:
                    break
                _b = self.rom[_p]
                if _b not in OPCODES:
                    break
                if _b == 0x00:
                    # Allow a single BRK within the sequence but count it
                    _brkseq += 1
                    if _brkseq > 1:
                        break  # two BRKs in a row = data boundary
                    _, _bsz, _ = OPCODES[_b]
                    _p += _bsz
                    continue
                _, _bsz, _ = OPCODES[_b]
                _p += _bsz
                _vseq += 1
                if _vseq >= _threshold:
                    break
            if _vseq >= _threshold:
                _bank = _next_off // self.bank_size if self.num_banks > 1 else 0
                _cpu_addr = 0xF000 + (_next_off % self.bank_size) if self.num_banks == 1 else \
                            (0xF000 + (_next_off % self.bank_size) if _bank == self.num_banks - 1 else
                             (0xE000 - (self.num_banks - 1 - _bank) * 0x1000) + (_next_off % self.bank_size))
                _post_terminal_seeds.append((_cpu_addr, _bank))
        if _post_terminal_seeds:
            self._worklist.extend(_post_terminal_seeds)
            # IMPORTANT: Phase 2.5 seeds may have been visited (but not executed)
            # during Phase 1 — for example, a branch path that landed on a BRK and
            # stopped adds the BRK's successor to visited but not to executed.
            # Remove those addresses from 'visited' so the Phase 2 worklist loop
            # will actually process them instead of skipping them.
            for (_seed_cpu, _seed_bank) in _post_terminal_seeds:
                _seed_pc13 = _seed_cpu & 0x1FFF
                if _seed_pc13 >= 0x1000:
                    _seed_rom_off = _seed_bank * self.bank_size + (_seed_pc13 - 0x1000)
                    visited.discard((_seed_rom_off, _seed_bank))

        # Continue executing with Phase 2 + any remaining worklist items
        while self._worklist and instruction_count < max_insns:
            start_pc, start_bank = self._worklist.pop()
            self.current_bank = start_bank
            self.PC = start_pc

            # Linear sweep from this entry point
            while instruction_count < max_insns:
                pc = self.PC & 0xFFFF
                pc13 = pc & 0x1FFF
                if pc13 < 0x1000:
                    break  # left ROM window

                rom_off = self._rom_offset(pc13)
                if rom_off >= rom_size:
                    break  # outside ROM data

                state = (rom_off, self.current_bank)
                if state in visited:
                    break  # already explored this path
                visited.add(state)

                opcode = self.rom[rom_off]
                if opcode not in OPCODES:
                    break  # invalid opcode = data

                # BRK ($00) is a valid 1-byte instruction on the 6507.
                # Record it as executed so the disassembler shows it as BRK,
                # then stop linear tracing (BRK jumps to IRQ vector).
                # Exception: 4+ consecutive $00 bytes = ROM fill padding.
                if opcode == 0x00:
                    if (rom_off + 3 < rom_size and
                            self.rom[rom_off + 1] == 0x00 and
                            self.rom[rom_off + 2] == 0x00 and
                            self.rom[rom_off + 3] == 0x00):
                        break  # ROM fill — not a real BRK instruction
                    # Single BRK: record as executed, stop linear path
                    self.executed.add(rom_off)
                    break
                if opcode == 0xFF:
                    if (rom_off + 3 < rom_size and
                            self.rom[rom_off + 1] == 0xFF and
                            self.rom[rom_off + 2] == 0xFF and
                            self.rom[rom_off + 3] == 0xFF):
                        break  # Four consecutive $FF = ROM fill, treat as data boundary

                mnemonic, size, mode = OPCODES[opcode]
                self.executed.add(rom_off)
                instruction_count += 1

                next_pc = (pc + size) & 0xFFFF
                op1 = pc + 1

                # ---- Control flow handling ----
                if mnemonic in ('BPL','BMI','BVC','BVS','BCC','BCS','BNE','BEQ'):
                    offset = self.mem_read(op1)
                    if offset >= 128: offset -= 256
                    branch_target = (pc + 2 + offset) & 0xFFFF
                    # Explore BOTH paths (we don't know register state)
                    self._worklist.append((next_pc, self.current_bank))
                    self._worklist.append((branch_target, self.current_bank))
                    break  # Both paths queued; stop linear sweep here

                elif mnemonic == 'JMP' and mode == 'absolute':
                    target = self.mem_read(op1) | (self.mem_read(op1 + 1) << 8)
                    self._worklist.append((target, self.current_bank))
                    break  # unconditional jump

                elif mnemonic == 'JMP' and mode == 'indirect':
                    # Resolve the JMP ($zp) or JMP ($addr) target.
                    # For zero-page pointers the target is in RAM (maintained by
                    # LDA/STA instructions executed along this path).
                    # For ROM-based vector tables (ptr >= $1000) read from ROM.
                    ptr = self.mem_read(op1) | (self.mem_read(op1 + 1) << 8)
                    ptr13 = ptr & 0x1FFF
                    if ptr13 >= 0x1000:
                        ptr_off = self._rom_offset(ptr13)
                        if ptr_off + 1 < rom_size:
                            lo = self.rom[ptr_off]
                            hi = self.rom[ptr_off + 1]
                            target = lo | (hi << 8)
                            self._worklist.append((target, self.current_bank))
                    else:
                        # Zero-page pointer — read target from RAM
                        lo = self.mem_read(ptr)
                        hi = self.mem_read((ptr + 1) & 0xFFFF)
                        target = lo | (hi << 8)
                        target13 = target & 0x1FFF
                        if target13 >= 0x1000:
                            self._worklist.append((target, self.current_bank))
                    # Dynamic dispatch table resolution: scan backwards in ROM
                    # for the LDA abs,Y/STA $zp pattern and walk all table entries.
                    # This discovers all Y-indexed dispatch targets dynamically.
                    dyn_seeds = self._resolve_indirect_jmp_via_tables(rom_off, self.current_bank)
                    self._worklist.extend(dyn_seeds)
                    break  # end linear sweep regardless

                elif mnemonic == 'JSR':
                    target = self.mem_read(op1) | (self.mem_read(op1 + 1) << 8)
                    # Queue the subroutine as a new path
                    self._worklist.append((target, self.current_bank))
                    # Continue fall-through after JSR (assume RTS returns here)
                    self.PC = next_pc
                    continue

                elif mnemonic in ('RTS', 'RTI', 'BRK'):
                    break  # end of this path

                else:
                    # Normal instruction: check for bank switch via mem_read side-effect
                    prev_bank = self.current_bank
                    # Execute side effects (for accuracy of bank-switch detection)
                    self.PC = next_pc
                    self._execute_noncf(mnemonic, mode, op1)
                    if self.current_bank != prev_bank:
                        # Bank switched - queue new context, stop current path
                        self._worklist.append((self.PC, self.current_bank))
                        break
                    continue

        # --- Phase 4: Sparse-region sweep ---
        # If a contiguous untraced region is large enough and passes a validity
        # check (< 20% invalid opcodes), it is almost certainly code accessed
        # via computed RAM pointers (JMP ($zp) where $zp is loaded at runtime).
        # These regions cannot be reached by static analysis of JSR/JMP
        # instructions, but they ARE real code.
        #
        # This applies to both flat 4K ROMs and banked ROMs.
        #
        # For banked ROMs we additionally sweep entire under-traced banks (< 10%
        # traced) regardless of whether there is a contiguous untraced segment.
        #
        # Safety checks before sweeping a region:
        #   1. The region is at least 16 bytes long.
        #   2. A quick validity check: sample up to 64 bytes — if > 20% are
        #      invalid opcodes (bytes not in OPCODES), skip (it's data).
        #   3. We stop within the sweep at 4+ consecutive $FF (ROM fill) or
        #      4+ consecutive $00 (BRK padding).

        def _validity_ok(start: int, end: int) -> bool:
            """Return True if the region looks like code (< 20% invalid opcodes).
            $00 (BRK) is treated as invalid since it appears in data/padding but
            almost never in the middle of real kernel code."""
            # Quick rejection: if the region starts with $00 it's padding/data
            if start < len(self.rom) and self.rom[start] == 0x00:
                return False
            sample_end = min(start + 64, end)
            invalid = 0
            valid   = 0
            spc = start
            while spc < sample_end:
                sb = self.rom[spc]
                # Treat $00 (BRK) as invalid — it's a data/padding byte in practice
                if sb not in OPCODES or sb == 0x00:
                    invalid += 1
                    spc += 1
                else:
                    _, ssz, _ = OPCODES[sb]
                    valid += 1
                    spc += ssz
            total = invalid + valid
            return total == 0 or (invalid / total) <= 0.20

        def _sweep_region(start: int, end: int) -> None:
            """Linear sweep of [start, end), adding valid instruction offsets."""
            pc4 = start
            stop_before = end - 6  # leave last 6 bytes (vectors) alone
            if stop_before <= start:
                stop_before = end
            while pc4 < stop_before:
                b4 = self.rom[pc4]
                # Stop on 4+ consecutive $FF (ROM fill)
                if b4 == 0xFF:
                    if (pc4 + 3 < end and
                            self.rom[pc4 + 1] == 0xFF and
                            self.rom[pc4 + 2] == 0xFF and
                            self.rom[pc4 + 3] == 0xFF):
                        while pc4 < end and self.rom[pc4] == 0xFF:
                            pc4 += 1
                        continue
                # Stop on 4+ consecutive $00 (BRK padding)
                if b4 == 0x00:
                    run00 = 0
                    j = pc4
                    while j < end and self.rom[j] == 0x00:
                        run00 += 1
                        j += 1
                    if run00 >= 4:
                        pc4 = j
                        continue
                if b4 not in OPCODES:
                    pc4 += 1
                    continue
                _, sz4, _ = OPCODES[b4]
                self.executed.add(pc4)
                pc4 += sz4

        # Pass A: sweep contiguous untraced segments ONLY when they are
        # sandwiched between two confirmed code regions AND are small (<= 32 bytes).
        # This handles the case where a short data table or padding sits between
        # two code blocks and causes the tracer to lose the thread.
        # We do NOT sweep large untraced regions speculatively — those are data.
        #
        # IMPORTANT: self.executed contains only INSTRUCTION START bytes, not
        # operand bytes. We must walk through instructions properly (using their
        # sizes) to avoid treating operand bytes of multi-byte instructions as
        # "untraced data gaps". We build a full coverage set first.
        all_covered: 'Set[int]' = set()
        for exec_off in self.executed:
            op_byte = self.rom[exec_off] if exec_off < rom_size else 0
            if op_byte in OPCODES:
                _, isz, _ = OPCODES[op_byte]
                for k in range(isz):
                    all_covered.add(exec_off + k)
            else:
                all_covered.add(exec_off)

        seg_start = None
        prev_was_code = False
        for off in range(rom_size):
            in_exec = off in all_covered
            if not in_exec:
                if seg_start is None:
                    seg_start = off
            else:
                if seg_start is not None and prev_was_code:
                    # Untraced segment between two code regions
                    seg_len = off - seg_start
                    # Only sweep very small gaps (likely padding/inline data in code)
                    if seg_len <= 32 and _validity_ok(seg_start, off):
                        _sweep_region(seg_start, off)
                    seg_start = None
                elif seg_start is not None:
                    seg_start = None  # gap at start or after data — skip
            prev_was_code = in_exec

        # Pass B: for banked ROMs, sweep entire under-traced banks.
        # Only applies to multi-bank ROMs — for single-bank ROMs a low trace
        # ratio is expected because the main game loop is typically entered via
        # a JMP stored in a RAM pointer (JMP ($zp)), which we can't follow
        # statically without knowing the runtime register state.
        # Sweeping single-bank ROMs speculatively causes sprite bitmap data
        # (which looks like valid-but-illegal opcodes) to be misclassified as code.
        if self.num_banks > 1:
            for bank_idx in range(self.num_banks):
                bank_start = bank_idx * self.bank_size
                bank_end   = min(bank_start + self.bank_size, rom_size)
                bank_bytes  = bank_end - bank_start
                traced_in_bank = sum(
                    1 for o in self.executed
                    if bank_start <= o < bank_end
                )
                trace_ratio = traced_in_bank / bank_bytes if bank_bytes > 0 else 1.0
                if trace_ratio >= 0.10:
                    continue  # already well-traced
                if _validity_ok(bank_start, bank_end):
                    _sweep_region(bank_start, bank_end)

        # --- Phase 4.5: repeat Phase 2.5 iteratively until stable ---
        # Phase 4 can add BRKs to executed that Phase 2.5 missed. Loop until stable.
        _p45_prev = -1
        while len(self.executed) != _p45_prev:
            _p45_prev = len(self.executed)
            _pt_seeds2 = []
            for _ro2 in sorted(self.executed):
                _op2 = self.rom[_ro2]
                if _op2 not in OPCODES:
                    continue
                _mn2, _sz2, _md2 = OPCODES[_op2]
                _isterm2 = _mn2 in ('RTS', 'RTI', 'BRK') or (_mn2 == 'JMP' and _md2 == 'absolute' and _sz2 == 3)
                if not _isterm2:
                    continue
                _no2 = _ro2 + _sz2
                if _no2 >= rom_size or _no2 in self.executed:
                    continue
                _thr2 = 5 if _mn2 == 'BRK' else 10
                _pp2 = _no2; _vs2 = 0; _bs2 = 0
                for _ in range(max(10, _thr2 + 2)):
                    if _pp2 >= rom_size: break
                    _bb2 = self.rom[_pp2]
                    if _bb2 not in OPCODES: break
                    if _bb2 == 0x00:
                        _bs2 += 1
                        if _bs2 > 1: break
                        _pp2 += 1; continue
                    _, _bbsz2, _ = OPCODES[_bb2]; _pp2 += _bbsz2; _vs2 += 1
                    if _vs2 >= _thr2: break
                if _vs2 >= _thr2:
                    _bk2 = _no2 // self.bank_size if self.num_banks > 1 else 0
                    if self.num_banks == 1:
                        _ca2 = 0xF000 + (_no2 % self.bank_size)
                    elif _bk2 == self.num_banks - 1:
                        _ca2 = 0xF000 + (_no2 % self.bank_size)
                    else:
                        _ca2 = (0xE000 - (self.num_banks - 1 - _bk2) * 0x1000) + (_no2 % self.bank_size)
                    _pt_seeds2.append((_ca2, _bk2))
            if not _pt_seeds2:
                break
            self._worklist = _pt_seeds2
            _vis2: 'Set[tuple]' = set()
            while self._worklist and instruction_count < max_insns:
                _spc2, _sbk2 = self._worklist.pop()
                self.current_bank = _sbk2; self.PC = _spc2
                while instruction_count < max_insns:
                    _pc2 = self.PC & 0xFFFF; _pc132 = _pc2 & 0x1FFF
                    if _pc132 < 0x1000: break
                    _ro_2 = self._rom_offset(_pc132)
                    if _ro_2 >= rom_size: break
                    _op_2 = self.rom[_ro_2]
                    if _op_2 == 0x00:
                        if not (_ro_2 + 3 < rom_size and self.rom[_ro_2+1] == 0 and self.rom[_ro_2+2] == 0 and self.rom[_ro_2+3] == 0):
                            self.executed.add(_ro_2)
                        break
                    _st2 = (_ro_2, self.current_bank)
                    if _st2 in _vis2: break
                    _vis2.add(_st2)
                    if _op_2 not in OPCODES: break
                    if _op_2 == 0xFF:
                        if _ro_2 + 3 < rom_size and self.rom[_ro_2+1] == 0xFF and self.rom[_ro_2+2] == 0xFF and self.rom[_ro_2+3] == 0xFF: break
                    _mn_2, _sz_2, _md_2 = OPCODES[_op_2]
                    self.executed.add(_ro_2); instruction_count += 1
                    _npc2 = (_pc2 + _sz_2) & 0xFFFF; _op12 = _pc2 + 1
                    if _mn_2 in ('BPL','BMI','BVC','BVS','BCC','BCS','BNE','BEQ'):
                        _off2 = self.mem_read(_op12)
                        if _off2 >= 128: _off2 -= 256
                        _bt2 = (_pc2 + 2 + _off2) & 0xFFFF
                        self._worklist.append((_npc2, self.current_bank)); self._worklist.append((_bt2, self.current_bank)); break
                    elif _mn_2 == 'JMP' and _md_2 == 'absolute':
                        _t2 = self.mem_read(_op12) | (self.mem_read(_op12+1) << 8)
                        self._worklist.append((_t2, self.current_bank)); break
                    elif _mn_2 == 'JSR':
                        _t2 = self.mem_read(_op12) | (self.mem_read(_op12+1) << 8)
                        self._worklist.append((_t2, self.current_bank)); self.PC = _npc2; continue
                    elif _mn_2 in ('RTS', 'RTI', 'BRK', 'JMP'): break
                    else:
                        _pb2 = self.current_bank; self.PC = _npc2; self._execute_noncf(_mn_2, _md_2, _op12)
                        if self.current_bank != _pb2: self._worklist.append((self.PC, self.current_bank)); break
                        continue

        return self.executed

    def _execute_noncf(self, mnemonic: str, mode: str, op1: int) -> None:
        """
        Execute the side-effects of a non-control-flow instruction.
        This updates registers/flags/RAM and triggers bank switches via mem_read.

        IMPORTANT: We must correctly update registers AND write actual values to RAM.
        This is critical for resolving JMP ($zp) targets: code like
          LDA #$04 / STA $80 / LDA #$F0 / STA $81 / JMP ($80)
        only works if STA writes the real A value to RAM (not 0).
        """
        ea = 0
        if mode == 'immediate':
            imm = self.mem_read(op1)
            if mnemonic == 'LDA': self.A = self._set_nz(imm)
            elif mnemonic == 'LDX': self.X = self._set_nz(imm)
            elif mnemonic == 'LDY': self.Y = self._set_nz(imm)
            elif mnemonic in ('AND','ORA','EOR'): pass  # affect A but we don't need to track
            # Immediate mode never triggers bank switches
            return

        if mode in ('absolute', 'absolute_x', 'absolute_y',
                    'zeropage', 'zeropage_x', 'zeropage_y',
                    'indirect_x', 'indirect_y'):
            ea = self._ea(mode, op1)

        if mnemonic == 'LDA':
            self.A = self._set_nz(self.mem_read(ea))  # mem_read triggers bank switch
        elif mnemonic == 'LDX':
            self.X = self._set_nz(self.mem_read(ea))
        elif mnemonic == 'LDY':
            self.Y = self._set_nz(self.mem_read(ea))
        elif mnemonic == 'LAX':
            self.A = self.X = self._set_nz(self.mem_read(ea))
        elif mnemonic == 'STA':
            self.mem_write(ea, self.A)   # write ACTUAL A value so RAM pointers are correct
        elif mnemonic == 'STX':
            self.mem_write(ea, self.X)
        elif mnemonic == 'STY':
            self.mem_write(ea, self.Y)
        elif mnemonic == 'SAX':
            self.mem_write(ea, self.A & self.X)
        elif mnemonic in ('BIT','CMP','CPX','CPY','AND','ORA','EOR',
                          'ADC','SBC','INC','DEC','ASL','LSR','ROL','ROR'):
            # For bank-switch detection: trigger the read
            if mode in ('absolute', 'absolute_x', 'absolute_y'):
                self.mem_read(ea)
        # TAX/TAY/TXA/TYA/INX/DEX/etc. have implied mode — handled above (mode not in list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate_rom(rom: bytearray, deep: bool = True, time_limit_sec: float = 180.0):
    """
    Execution-trace *rom* and return execution results.

    Runs multiple passes with different initial register states (A, X, Y seeds)
    until either no new addresses are found or the time limit is reached.
    Each pass shares the growing executed set from all previous passes, so
    new passes only explore paths not yet covered.

    This exhaustive multi-pass approach handles ROMs where:
    - Branches depend on runtime register values (BEQ/BNE with unknown flags)
    - JMP ($zp) target depends on which code path set the pointer
    - Different X/Y values index different entries in dispatch tables
    - Conditional code paths that are only taken with specific register values

    Args:
        rom:           ROM data (bytearray, any supported size)
        deep:          If True (default), use deep analysis; False = fast single pass
        time_limit_sec: Max wall-clock seconds to spend (default: 180 = 3 minutes).
                        Set to 0 for unlimited (not recommended for large ROMs).

    Returns:
        Tuple of:
          - Set[int]: ROM byte-offsets for instruction starts actually executed
          - Set[int]: CPU addresses of indirect-dispatch table targets
                      (these need Jump_ labels even though no JSR/JMP abs refs them)
    """
    import time
    import itertools

    start_time = time.monotonic()

    # --- Pass 0: standard trace (no register seeding) ---
    cpu0 = CPU6507(rom, deep=deep)
    executed = cpu0.run()
    dispatch_targets = set(cpu0.dispatch_targets)

    if not deep:
        # Fast mode: single pass only
        return executed, dispatch_targets

    # --- Multi-pass exhaustive exploration ---
    # Generate register seed combinations to try.
    # We vary A, X, Y across a set of representative values:
    #   0x00 (zero), 0x01 (one), 0x7F (max positive), 0x80 (min negative),
    #   0xFF (max), and a few game-specific values (0x02, 0x10, 0x20).
    # We also try different initial bank states for banked ROMs.
    reg_values = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40,
                  0x7F, 0x80, 0xC0, 0xFF]
    # For efficiency, generate seeds as (A, X, Y) triples.
    # We don't try all 12^3 = 1728 combinations — instead use a smart
    # selection: vary one register at a time (36 seeds) plus diagonal
    # (all three same: 12 seeds) = 48 total passes max.
    seeds = []
    for v in reg_values:
        seeds.append((v,    0x00, 0x00))   # vary A
        seeds.append((0x00, v,    0x00))   # vary X
        seeds.append((0x00, 0x00, v   ))   # vary Y
        seeds.append((v,    v,    v   ))   # all same

    # Remove duplicates while preserving order
    seen_seeds = set()
    unique_seeds = []
    for s in seeds:
        if s not in seen_seeds:
            seen_seeds.add(s)
            unique_seeds.append(s)

    pass_num = 0
    total_passes = len(unique_seeds)
    prev_count = len(executed)

    for (a_seed, x_seed, y_seed) in unique_seeds:
        elapsed = time.monotonic() - start_time
        if time_limit_sec > 0 and elapsed >= time_limit_sec:
            print(f"  [exhaustive] Time limit {time_limit_sec:.0f}s reached after {pass_num} passes "
                  f"({len(executed)} offsets found)")
            break

        pass_num += 1

        # Create a new CPU instance with the seeded register values
        cpu_n = CPU6507(rom, deep=deep)
        cpu_n.A = a_seed
        cpu_n.X = x_seed
        cpu_n.Y = y_seed
        # Pre-seed RAM with the X and Y values so indexed loads return
        # the seed value (simulates "the game is mid-loop with X=n")
        for addr in range(0x80, 0x100):
            cpu_n.ram[addr - 0x80] = x_seed  # zero-page RAM

        # Share the executed set: new pass only needs to explore NEW addresses.
        # We DON'T pre-populate cpu_n.executed with the existing set because
        # the visited set uses (rom_off, bank) tuples — if we pre-populate
        # executed, the visited check still works correctly (it's independent).
        # Instead we pre-populate the visited set so we skip already-traced paths.
        # Actually the cleanest approach: run the full pass and merge afterward.
        cpu_n.run()

        # Merge new findings
        new_offsets = cpu_n.executed - executed
        if new_offsets:
            executed.update(new_offsets)
            dispatch_targets.update(cpu_n.dispatch_targets)

        # Early termination: if we haven't found new addresses in the last
        # several passes, the ROM is likely fully explored.
        if pass_num % 8 == 0:
            new_count = len(executed)
            if new_count == prev_count:
                print(f"  [exhaustive] No new offsets in last 8 passes — stopping early "
                      f"(pass {pass_num}/{total_passes}, {len(executed)} offsets)")
                break
            prev_count = new_count

    elapsed = time.monotonic() - start_time
    print(f"  [exhaustive] {pass_num} passes in {elapsed:.1f}s → {len(executed)} offsets "
          f"({len(executed)/len(rom)*100:.1f}% of ROM)")

    return executed, dispatch_targets
