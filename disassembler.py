"""
Smart 6502 Disassembler with Code Flow Analysis

Advanced Atari 2600 disassembler that intelligently distinguishes between code and data.
Features:
- Code flow analysis to separate code from data
- Automatic label generation for subroutines and branches
- Variable tracking for zero-page RAM usage
- Pattern recognition (delay loops, sprite kernels, etc.)
- Bank switching detection
- Cross-reference analysis
- Cycle counting
- Graphics data visualization

Created by Jeff Molofee (NeHe) 2026
"""

import os
from typing import Dict, Set, List, Tuple, Optional

# Import from consolidated modules
from core_opcodes import OPCODES, get_opcode_flags, get_opcode_operation, format_flags_comment, format_operation_comment, format_cycles
from symbols_and_tracking import get_symbol_name, get_all_symbols, get_instruction_comment, get_section_comment, VariableTracker, CrossReferencer
from analyzers import get_data_region_comment, get_code_section_comment, analyze_code_section, PatternRecognizer
from banking import BankSwitcher
from cpu_simulator import simulate_rom

# ============================================================================
# Official 6502/6507 opcode bytes (standard, non-illegal).
# Any opcode byte NOT in this set will be emitted as .byte in the output
# to ensure byte-exact round-trip assembly (the assembler only knows these).
OFFICIAL_6502_OPCODES = frozenset({
    0x00, 0x01, 0x05, 0x06, 0x08, 0x09, 0x0A, 0x0D, 0x0E,
    0x10, 0x11, 0x15, 0x16, 0x18, 0x19, 0x1D, 0x1E,
    0x20, 0x21, 0x24, 0x25, 0x26, 0x28, 0x29, 0x2A, 0x2C, 0x2D, 0x2E,
    0x30, 0x31, 0x35, 0x36, 0x38, 0x39, 0x3D, 0x3E,
    0x40, 0x41, 0x45, 0x46, 0x48, 0x49, 0x4A, 0x4C, 0x4D, 0x4E,
    0x50, 0x51, 0x55, 0x56, 0x58, 0x59, 0x5D, 0x5E,
    0x60, 0x61, 0x65, 0x66, 0x68, 0x69, 0x6A, 0x6C, 0x6D, 0x6E,
    0x70, 0x71, 0x75, 0x76, 0x78, 0x79, 0x7D, 0x7E,
    0x81, 0x84, 0x85, 0x86, 0x88, 0x8A, 0x8C, 0x8D, 0x8E,
    0x90, 0x91, 0x94, 0x95, 0x96, 0x98, 0x99, 0x9A, 0x9D,
    0xA0, 0xA1, 0xA2, 0xA4, 0xA5, 0xA6, 0xA8, 0xA9, 0xAA, 0xAC, 0xAD, 0xAE,
    0xB0, 0xB1, 0xB4, 0xB5, 0xB6, 0xB8, 0xB9, 0xBA, 0xBC, 0xBD, 0xBE,
    0xC0, 0xC1, 0xC4, 0xC5, 0xC6, 0xC8, 0xC9, 0xCA, 0xCC, 0xCD, 0xCE,
    0xD0, 0xD1, 0xD5, 0xD6, 0xD8, 0xD9, 0xDD, 0xDE,
    0xE0, 0xE1, 0xE4, 0xE5, 0xE6, 0xE8, 0xE9, 0xEA, 0xEC, 0xED, 0xEE,
    0xF0, 0xF1, 0xF5, 0xF6, 0xF8, 0xF9, 0xFD, 0xFE,
})

# ============================================================================

def read_word(rom: bytearray, offset: int) -> int:
    """
    Read a 16-bit word (little-endian) from ROM.
    
    Args:
        rom: ROM data as bytearray
        offset: Offset to read from
        
    Returns:
        16-bit word value
    """
    return rom[offset] | (rom[offset + 1] << 8)

def format_operand(mode: str, operand_bytes: bytes, pc: int, labels: Optional[Dict[int, str]] = None, var_tracker: Optional['VariableTracker'] = None, rom_offset: Optional[int] = None, rom_size: Optional[int] = None, bank_scheme: Optional[str] = None, bank_count: Optional[int] = None, bank_size: Optional[int] = None) -> str:
    """
    Format operand based on addressing mode, using symbols, variables, and labels where possible.
    
    Args:
        mode: Addressing mode (e.g., 'immediate', 'absolute', 'zeropage')
        operand_bytes: Operand bytes from instruction
        pc: Program counter (current address)
        labels: Optional dictionary mapping addresses to label names
        var_tracker: Optional VariableTracker for zero-page variable names
        rom_offset: Optional ROM offset for bank-aware branch calculation
        rom_size: Optional ROM size for bank-aware branch calculation
        bank_scheme: Optional bank scheme for bank-aware branch calculation
        bank_count: Optional bank count for bank-aware branch calculation
        bank_size: Optional bank size for bank-aware branch calculation
        
    Returns:
        Formatted operand string
    """
    if mode == 'implied' or mode == 'accumulator':
        return ''
    elif mode == 'immediate':
        return f'#${operand_bytes[0]:02X}'
    elif mode == 'zeropage':
        addr = operand_bytes[0]
        # Check for variable name first (RAM area $80-$FF)
        if var_tracker and 0x80 <= addr <= 0xFF:
            var_name = var_tracker.get_variable_name(addr)
            if var_name:
                return f'<{var_name}'
        # Then check for hardware symbol
        symbol = get_symbol_name(addr)
        # Use < prefix to explicitly indicate zeropage mode for assembler
        return f'<{symbol}' if symbol else f'${addr:02X}'
    elif mode == 'zeropage_x':
        addr = operand_bytes[0]
        # Check for variable name first (RAM area $80-$FF)
        if var_tracker and 0x80 <= addr <= 0xFF:
            var_name = var_tracker.get_variable_name(addr)
            if var_name:
                return f'<{var_name},X'
        # Then check for hardware symbol
        symbol = get_symbol_name(addr)
        # Use < prefix to explicitly indicate zeropage mode for assembler
        return f'<{symbol},X' if symbol else f'${addr:02X},X'
    elif mode == 'zeropage_y':
        addr = operand_bytes[0]
        # Check for variable name first (RAM area $80-$FF)
        if var_tracker and 0x80 <= addr <= 0xFF:
            var_name = var_tracker.get_variable_name(addr)
            if var_name:
                return f'<{var_name},Y'
        # Then check for hardware symbol
        symbol = get_symbol_name(addr)
        # Use < prefix to explicitly indicate zeropage mode for assembler
        return f'<{symbol},Y' if symbol else f'${addr:02X},Y'
    elif mode == 'absolute':
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        # Check for label first, then hardware symbol
        if labels and addr in labels:
            return labels[addr]
        symbol = get_symbol_name(addr)
        return symbol if symbol else f'${addr:04X}'
    elif mode == 'absolute_x':
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        symbol = get_symbol_name(addr)
        return f'{symbol},X' if symbol else f'${addr:04X},X'
    elif mode == 'absolute_y':
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        symbol = get_symbol_name(addr)
        return f'{symbol},Y' if symbol else f'${addr:04X},Y'
    elif mode == 'indirect':
        addr = operand_bytes[0] | (operand_bytes[1] << 8)
        return f'(${addr:04X})'
    elif mode == 'indirect_x':
        return f'(${operand_bytes[0]:02X},X)'
    elif mode == 'indirect_y':
        return f'(${operand_bytes[0]:02X}),Y'
    elif mode == 'relative':
        offset = operand_bytes[0]
        if offset >= 128:
            offset = offset - 256
        
        # For banked ROMs, calculate target using ROM offset and bank info
        if rom_offset is not None and rom_size is not None and bank_scheme and bank_count and bank_size:
            target_offset = rom_offset + 2 + offset
            if 0 <= target_offset < rom_size:
                _, target = get_bank_info_for_offset(target_offset, rom_size, bank_scheme, bank_count, bank_size)
            else:
                target = (pc + 2 + offset) & 0xFFFF
        else:
            target = (pc + 2 + offset) & 0xFFFF
        
        # Check for label
        if labels and target in labels:
            return labels[target]
        return f'${target:04X}'
    return ''

def find_data_accessors(rom: bytearray, code_addresses: Set[int], base_addr: int) -> Dict[int, List[str]]:
    """
    NEW: TIA Register Write Tracking and Data Flow Tracing
    
    Tracks all TIA register writes and traces backward to find ROM data sources.
    This allows automatic labeling of ROM data based on actual hardware usage.
    
    Algorithm:
    1. Scan all code for STA/STX/STY instructions to TIA registers
    2. For each TIA write, scan backward (1-10 instructions) to find the source
    3. If source is LDA/LDX/LDY from ROM (absolute or indexed), record it
    4. Build a map: ROM_address -> [list of TIA register names it feeds]
    
    Args:
        rom: ROM data as bytearray
        code_addresses: Set of offsets identified as code
        base_addr: Base address where ROM is loaded in memory
        
    Returns:
        Dictionary mapping ROM data addresses to list of TIA register names
        Example: {0xF800: ['GRP0', 'GRP1'], 0xF900: ['AUDC0', 'AUDV0']}
    """
    rom_size = len(rom)
    data_usage = {}  # ROM_addr -> [TIA_register_names]
    
    # TIA register categories (from symbols_and_tracking.py)
    TIA_GRAPHICS = {0x1B: 'GRP0', 0x1C: 'GRP1', 0x0D: 'PF0', 0x0E: 'PF1', 0x0F: 'PF2'}
    TIA_COLOR = {0x06: 'COLUP0', 0x07: 'COLUP1', 0x08: 'COLUPF', 0x09: 'COLUBK'}
    TIA_AUDIO = {0x15: 'AUDC0', 0x16: 'AUDC1', 0x17: 'AUDF0', 0x18: 'AUDF1', 0x19: 'AUDV0', 0x1A: 'AUDV1'}
    TIA_POSITION = {0x10: 'RESP0', 0x11: 'RESP1', 0x12: 'RESM0', 0x13: 'RESM1', 0x14: 'RESBL'}
    TIA_MOTION = {0x20: 'HMP0', 0x21: 'HMP1', 0x22: 'HMM0', 0x23: 'HMM1', 0x24: 'HMBL'}
    TIA_CONTROL = {0x0A: 'CTRLPF', 0x0B: 'REFP0', 0x0C: 'REFP1', 0x25: 'VDELP0', 0x26: 'VDELP1', 0x27: 'VDELBL'}
    
    # Combine all TIA registers
    ALL_TIA = {}
    ALL_TIA.update(TIA_GRAPHICS)
    ALL_TIA.update(TIA_COLOR)
    ALL_TIA.update(TIA_AUDIO)
    ALL_TIA.update(TIA_POSITION)
    ALL_TIA.update(TIA_MOTION)
    ALL_TIA.update(TIA_CONTROL)
    
    print(f"\n=== TIA Register Write Tracking ===")
    
    # Scan through all code looking for TIA writes
    tia_writes_found = 0
    rom_data_sources = 0
    
    for pc in range(rom_size):
        if pc not in code_addresses:
            continue
        
        opcode = rom[pc]
        if opcode not in OPCODES:
            continue
        
        mnemonic, size, mode = OPCODES[opcode]
        
        # Check for STA/STX/STY to TIA registers (zeropage addressing)
        if mnemonic in ['STA', 'STX', 'STY'] and mode == 'zeropage' and size >= 2:
            tia_addr = rom[pc + 1]
            
            # Is this a TIA register?
            if tia_addr in ALL_TIA:
                tia_name = ALL_TIA[tia_addr]
                tia_writes_found += 1
                
                # Now trace backward to find where the data came from
                # Scan previous 1-20 instructions
                scan_range = 20
                found_source = False
                
                # Map store instruction to corresponding load instruction
                load_mnemonic = {'STA': 'LDA', 'STX': 'LDX', 'STY': 'STY'}[mnemonic]
                
                # Scan backward from current instruction
                scan_pc = pc - 1
                instructions_scanned = 0
                indirect_zp = None  # If we find LDA (zp),Y, remember the zp addr
                
                while scan_pc >= 0 and instructions_scanned < scan_range:
                    # Must be in code addresses
                    if scan_pc not in code_addresses:
                        scan_pc -= 1
                        continue
                    
                    scan_opcode = rom[scan_pc]
                    if scan_opcode not in OPCODES:
                        scan_pc -= 1
                        continue
                    
                    scan_mnemonic, scan_size, scan_mode = OPCODES[scan_opcode]
                    
                    # Look for matching load instruction
                    if scan_mnemonic == load_mnemonic:
                        # Check if it's loading from ROM (absolute or absolute indexed)
                        if scan_mode in ['absolute', 'absolute_x', 'absolute_y'] and scan_size == 3:
                            # Get the ROM address being accessed
                            source_addr = rom[scan_pc + 1] | (rom[scan_pc + 2] << 8)
                            
                            # Validate it's in ROM range (not TIA/RIOT/RAM)
                            if source_addr >= base_addr and source_addr < base_addr + rom_size:
                                # For INDEXED loads (abs,X or abs,Y), mark the base address
                                # with a special sentinel so the label/header still works,
                                # but DON'T annotate individual bytes (we don't know which
                                # index value the CPU will use at runtime — any byte in the
                                # table could feed this register).
                                # For DIRECT loads (abs, non-indexed), we know the exact byte.
                                is_indexed = scan_mode in ['absolute_x', 'absolute_y']
                                
                                if source_addr not in data_usage:
                                    data_usage[source_addr] = []
                                
                                if tia_name not in data_usage[source_addr]:
                                    data_usage[source_addr].append(tia_name)
                                    rom_data_sources += 1
                                    print(f"  ${base_addr + pc:04X}: {mnemonic} {tia_name} <- {load_mnemonic} ${source_addr:04X} ({'indexed' if is_indexed else 'direct'}) (data feeds {tia_name})")
                                
                                # For indexed loads, also record a flag so the per-byte
                                # annotation is suppressed (only the block header gets the label).
                                # We encode this by storing a special marker alongside the name.
                                if is_indexed:
                                    marker = f'~{tia_name}'  # tilde prefix = indexed, no per-byte annotation
                                    if marker not in data_usage[source_addr]:
                                        data_usage[source_addr].append(marker)
                                
                                found_source = True
                                break
                        
                        # Check for indirect indexed: LDA (zp),Y or LDA (zp,X)
                        elif scan_mode in ['indirect_y', 'indirect_x'] and scan_size == 2:
                            indirect_zp = rom[scan_pc + 1]  # Zero-page address holding the pointer
                            found_source = True  # Mark as found (via pointer)
                            break
                    
                    # Move to previous instruction (scan backward through code)
                    scan_pc -= 1
                    instructions_scanned += 1
                
                # If we found an indirect load, now scan the whole ROM for where
                # the pointer (indirect_zp) gets set to a ROM address (LDA #hi / STA zp+1)
                if not found_source and indirect_zp is None:
                    pass  # No source found at all
                elif indirect_zp is not None:
                    # Search for patterns that set this pointer to a ROM address
                    # Pattern 1: LDA #<addr_lo / STA indirect_zp then LDA #>addr_hi / STA indirect_zp+1
                    # Pattern 2: LDA #>addr_hi / STA indirect_zp+1 (high byte store)
                    zp_hi = indirect_zp + 1  # High byte of pointer pair
                    
                    for search_pc in range(rom_size - 1):
                        if search_pc not in code_addresses:
                            continue
                        s_opcode = rom[search_pc]
                        if s_opcode not in OPCODES:
                            continue
                        s_mn, s_sz, s_mode = OPCODES[s_opcode]
                        
                        # Look for: LDA #imm / STA zp+1 (storing high byte of pointer)
                        if s_mn == 'LDA' and s_mode == 'immediate' and s_sz == 2:
                            hi_byte = rom[search_pc + 1]
                            # Check next instruction for STA to our pointer's high byte
                            next_pc2 = search_pc + 2
                            if next_pc2 < rom_size and next_pc2 in code_addresses:
                                n_op = rom[next_pc2]
                                if n_op in OPCODES:
                                    n_mn, n_sz, n_mode = OPCODES[n_op]
                                    if n_mn == 'STA' and n_mode == 'zeropage' and n_sz == 2:
                                        target_zp = rom[next_pc2 + 1]
                                        if target_zp == zp_hi:
                                            # High byte of pointer = hi_byte
                                            # This means data is at hi_byte << 8 (+ some lo byte)
                                            source_addr = hi_byte << 8
                                            # Validate it's in ROM range
                                            if source_addr >= base_addr and source_addr < base_addr + rom_size:
                                                if source_addr not in data_usage:
                                                    data_usage[source_addr] = []
                                                if tia_name not in data_usage[source_addr]:
                                                    data_usage[source_addr].append(tia_name)
                                                    rom_data_sources += 1
                                                    print(f"  ${base_addr + pc:04X}: {mnemonic} {tia_name} <- LDA (${indirect_zp:02X}),Y [ptr hi=${hi_byte:02X}xx] (data feeds {tia_name})")
                        
                        # Also look for: LDX #imm / STX zp+1 (high byte via X)
                        elif s_mn == 'LDX' and s_mode == 'immediate' and s_sz == 2:
                            hi_byte = rom[search_pc + 1]
                            next_pc2 = search_pc + 2
                            if next_pc2 < rom_size and next_pc2 in code_addresses:
                                n_op = rom[next_pc2]
                                if n_op in OPCODES:
                                    n_mn, n_sz, n_mode = OPCODES[n_op]
                                    if n_mn == 'STX' and n_mode == 'zeropage' and n_sz == 2:
                                        target_zp = rom[next_pc2 + 1]
                                        if target_zp == zp_hi:
                                            source_addr = hi_byte << 8
                                            if source_addr >= base_addr and source_addr < base_addr + rom_size:
                                                if source_addr not in data_usage:
                                                    data_usage[source_addr] = []
                                                if tia_name not in data_usage[source_addr]:
                                                    data_usage[source_addr].append(tia_name)
                                                    rom_data_sources += 1
                                                    print(f"  ${base_addr + pc:04X}: {mnemonic} {tia_name} <- LDA (${indirect_zp:02X}),Y [ptr hi=${hi_byte:02X}xx via X] (data feeds {tia_name})")
    
    print(f"  Total TIA writes found: {tia_writes_found}")
    print(f"  ROM data sources identified: {rom_data_sources}")
    print(f"  Unique ROM addresses: {len(data_usage)}")
    
    return data_usage

def analyze_code_flow(rom: bytearray, base_addr: int) -> Set[int]:
    """
    Perform code flow analysis to identify code vs data regions.

    Single-pass recursive descent from the RESET vector, following:
    - JSR/JMP targets
    - Branch targets (both sides)
    - Interrupt vectors (RESET only for 6507)

    The CPU simulator (cpu_simulator.py) handles the heavy lifting of
    finding all reachable code; this pass is a fast initial seed.
    TIA register backward-trace (find_data_accessors) still runs on top.

    Args:
        rom: ROM data as bytearray
        base_addr: Base address where ROM is loaded in memory

    Returns:
        Tuple of (code_addresses, tia_data_map)
        - code_addresses: Set of ROM offsets identified as instruction starts
        - tia_data_map: Dict mapping ROM addresses to TIA register names
    """
    rom_size = len(rom)
    code_addresses: Set[int] = set()
    code_bytes:     Set[int] = set()
    to_analyze = []

    # Determine bank layout from ROM size
    if rom_size <= 4096:
        _bank_count = 1
        _bank_size  = rom_size
    elif rom_size == 8192:
        _bank_count = 2; _bank_size = 4096
    elif rom_size == 12288:
        _bank_count = 3; _bank_size = 4096
    elif rom_size == 16384:
        _bank_count = 4; _bank_size = 4096
    elif rom_size == 32768:
        _bank_count = 8; _bank_size = 4096
    else:
        _bank_count = max(1, rom_size // 4096); _bank_size = 4096

    # Read RESET vector from last bank ($FFFC-$FFFD)
    reset_vector = read_word(rom, rom_size - 4)
    print(f"6507 Interrupt Vector:")
    print(f"  RESET: ${reset_vector:04X}")

    def _resolve_vector(vec_addr):
        """Map a CPU vector address to a ROM offset."""
        if _bank_count == 1:
            off = vec_addr - base_addr
            return off if 0 <= off < rom_size else None
        if 0xF000 <= vec_addr <= 0xFFFF:
            last_start = (_bank_count - 1) * _bank_size
            return last_start + (vec_addr - 0xF000)
        for bk in range(_bank_count - 1):
            dist = (_bank_count - 1) - bk
            bk_start = 0xE000 - dist * 0x1000
            bk_end   = bk_start + _bank_size
            if bk_start <= vec_addr < bk_end:
                return bk * _bank_size + (vec_addr - bk_start)
        return None

    start_pc = _resolve_vector(reset_vector)
    if start_pc is not None and 0 <= start_pc < rom_size:
        to_analyze.append(start_pc)
        print(f"  RESET vector points to: ${reset_vector:04X} (ROM offset ${start_pc:04X})")
    else:
        print(f"  RESET vector ${reset_vector:04X}: could not resolve to a ROM offset (ignored)")
        # Fallback: scan bank starts for plausible entry points
        RESET_START_OPCODES = {0x78, 0xD8, 0xA2, 0xA9, 0x4C, 0x6C}
        for bk in range(_bank_count):
            bk_off = bk * _bank_size
            if bk_off < rom_size and rom[bk_off] in RESET_START_OPCODES:
                to_analyze.append(bk_off)
                bk_addr = 0xF000 if bk == _bank_count - 1 else (0xE000 - ((_bank_count-1)-bk)*0x1000)
                print(f"  Fallback entry: bank {bk} start ${bk_addr:04X} (ROM offset ${bk_off:04X})")

    # ----------------------------------------------------------------
    # Single-pass recursive descent
    # ----------------------------------------------------------------
    print(f"\n=== Code Flow Analysis (single pass) ===")
    analyzed: Set[int] = set()

    def _target_offset(cpu_addr):
        """Convert a CPU address to a ROM offset (same logic as _resolve_vector)."""
        if _bank_count == 1:
            off = cpu_addr - base_addr
            return off if 0 <= off < rom_size else None
        if 0xF000 <= cpu_addr <= 0xFFFF:
            last = (_bank_count - 1) * _bank_size
            return last + (cpu_addr - 0xF000)
        for bk in range(_bank_count - 1):
            dist = (_bank_count - 1) - bk
            bs = 0xE000 - dist * 0x1000
            be = bs + _bank_size
            if bs <= cpu_addr < be:
                return bk * _bank_size + (cpu_addr - bs)
        return None

    while to_analyze:
        pc = to_analyze.pop(0)
        if pc in analyzed or pc < 0 or pc >= rom_size:
            continue
        analyzed.add(pc)

        while pc < rom_size and pc not in code_addresses:
            opcode = rom[pc]
            if opcode not in OPCODES:
                break
            mnemonic, size, mode = OPCODES[opcode]
            code_addresses.add(pc)
            for i in range(size):
                if pc + i < rom_size:
                    code_bytes.add(pc + i)

            if mnemonic in ('JSR', 'JMP') and size == 3 and pc + 2 < rom_size:
                tgt_addr = read_word(rom, pc + 1)
                tgt_off  = _target_offset(tgt_addr)
                if tgt_off is not None and 0 <= tgt_off < rom_size and tgt_off not in analyzed:
                    to_analyze.append(tgt_off)

            elif mnemonic in ('BPL','BMI','BVC','BVS','BCC','BCS','BNE','BEQ') and pc+1 < rom_size:
                rel = rom[pc + 1]
                if rel >= 128: rel -= 256
                tgt_off = pc + 2 + rel
                if 0 <= tgt_off < rom_size and tgt_off not in analyzed:
                    to_analyze.append(tgt_off)

            pc += size
            if mnemonic in ('RTS', 'RTI'):
                break
            if mnemonic == 'JMP' and mode == 'absolute':
                break

    print(f"  Static pass found {len(code_addresses)} instruction starts")

    # ----------------------------------------------------------------
    # TIA register write tracking (backward trace for data labeling)
    # Still runs on top of the sim-merged code_addresses in
    # disassemble_smart() after simulation merge.
    # We run it here on static results only as a quick seed.
    # ----------------------------------------------------------------
    tia_data_map = find_data_accessors(rom, code_addresses, base_addr)

    return code_addresses, tia_data_map

def calculate_alignment_column() -> int:
    """
    Calculate the column position where = and ; should align.
    
    Returns:
        Column number for alignment (50)
    """
    # Fixed alignment column for symbols and variables
    # This ensures = and comments are always in the same position
    # regardless of command-line options (--addresses, --hex, etc.)
    # Symbol/variable lines: name (18 chars) + " = $" (4 chars) + value (2-4 chars) = ~24-26 chars
    # We want comments to start at column 50 for readability
    return 50

def get_bank_info_for_offset(offset: int, rom_size: int, bank_scheme: Optional[str], bank_count: int, bank_size: int) -> Tuple[int, int]:
    """
    Get bank number and memory address for a ROM offset.
    
    Args:
        offset: ROM offset (0 to rom_size-1)
        rom_size: Total ROM size
        bank_scheme: Bank switching scheme (F8, F6, etc.) or None
        bank_count: Number of banks
        bank_size: Size of each bank
        
    Returns:
        Tuple of (bank_number, memory_address)
    """
    if not bank_scheme or rom_size <= 4096:
        # Non-banked ROM
        base_addr = 0x10000 - rom_size
        return (0, base_addr + offset)
    
    # For F8/F6/F4/FA schemes the ROM is split into equal 4K banks.
    # The last bank always lives at $F000-$FFFF (always mapped).
    # Earlier banks each get a unique $1000-aligned window so that their
    # ORG directives don't collide in the assembled output:
    #
    #   bank_count  bank 0     bank 1     bank 2     ...  bank N-1
    #   2 (F8)      $D000      $F000
    #   3 (FA)      $C000      $D000      $F000
    #   4 (F6)      $C000      $D000      $E000           $F000
    #   8 (F4)      $8000 ...  (each 4K step up)         $F000
    #
    # We assign addresses working backwards from $E000 (one page below $F000)
    # for the second-to-last bank, $D000 for the one before that, etc.
    bank_num = offset // bank_size
    offset_in_bank = offset % bank_size
    
    if bank_num == bank_count - 1:
        # Last bank always at $F000
        mem_addr = 0xF000 + offset_in_bank
    else:
        # Earlier banks get unique $1000-aligned windows below $F000.
        # The second-to-last bank always gets $D000 so that F8 (2-bank) ROMs keep
        # their traditional Bank-0 address of $D000.
        # For more banks we step further down: third-to-last → $C000, etc.
        #
        #   bank_count  bank 0      bank 1      bank N-1
        #   2  (F8)     $D000                   $F000
        #   3  (FA)     $C000       $D000        $F000
        #   4  (F6)     $C000       $D000  $E000 $F000
        #
        # Formula: second-to-last (distance=1) → $D000
        #          third-to-last  (distance=2) → $C000
        #          etc.
        distance_from_last = (bank_count - 1) - bank_num   # 1, 2, 3 …
        mem_addr = (0xE000 - distance_from_last * 0x1000) + offset_in_bank
    
    return (bank_num, mem_addr)

def disassemble_smart(rom_path: str, output_path: str) -> None:
    """
    Disassemble ROM with intelligent code/data separation.
    
    Main disassembly function that:
    1. Analyzes code flow to separate code from data
    2. Tracks zero-page variables
    3. Detects bank switching
    4. Recognizes code patterns
    5. Generates cross-references
    6. Outputs formatted assembly with comments
    
    Args:
        rom_path: Path to ROM file to disassemble
        output_path: Path to output assembly file
    """
    # Use global configuration variables (set by command-line arguments)
    global SHOW_LABELS, SHOW_XREFS, SHOW_CYCLES, SHOW_COMMENTS, SHOW_ADDRESSES, SHOW_HEX, VISUALIZE_DATA
    
    with open(rom_path, 'rb') as f:
        rom = bytearray(f.read())

    rom_size = len(rom)
    
    # IMPORTANT: For banked ROMs, we need the correct base address
    # Standard Atari 2600 cartridge mapping:
    # - 2K: $F800-$FFFF
    # - 4K: $F000-$FFFF
    # - 8K F8: Bank 0 at $D000-$DFFF, Bank 1 at $F000-$FFFF (but we analyze linearly)
    # - 16K F6: Banks at $D000-$DFFF, last bank at $F000-$FFFF
    # For initial analysis, we treat the ROM as linear starting at the appropriate base
    if rom_size <= 4096:
        base_addr = 0x10000 - rom_size
    else:
        # For banked ROMs, use $D000 as base for analysis
        # This allows proper address calculation during code flow
        base_addr = 0xD000
    
    rom_name = os.path.basename(rom_path)
    
    print(f"ROM size: {rom_size} bytes")
    print(f"Base address for analysis: ${base_addr:04X}")
    
    # Detect bank switching FIRST (before code flow analysis)
    print("\n=== Bank Switching Detection ===")
    bank_switcher = BankSwitcher()
    bank_scheme = bank_switcher.detect_scheme(rom, set())  # Initial detection without code addresses
    
    if bank_scheme:
        bank_info = bank_switcher.get_bank_info()
        print(f"Detected: {bank_info['description']}")
        print(f"Banks: {bank_info['banks']}, Bank Size: {bank_info['bank_size']} bytes")
    else:
        print("No bank switching detected (4K or smaller ROM)")
        bank_info = None
    
    # Analyze code flow (using linear ROM with base address)
    print("\n=== Code Flow Analysis ===")
    code_addresses, tia_data_map = analyze_code_flow(rom, base_addr)
    
    # Analyze zero page variable usage
    print("\n=== Variable Analysis ===")
    var_tracker = VariableTracker()
    var_tracker.analyze_code(rom, code_addresses, base_addr)
    
    variables = var_tracker.get_all_variables()
    pointer_pairs = var_tracker.get_pointer_pairs()
    
    print(f"Found {len(variables)} zero page variables")
    if pointer_pairs:
        print(f"Found {len(pointer_pairs)} pointer pairs: {pointer_pairs}")
    
    # Re-analyze bank switching with code addresses for hotspot detection
    if bank_scheme:
        bank_switcher.detect_scheme(rom, code_addresses)
        bank_info = bank_switcher.get_bank_info()
        if bank_info['hotspot_accesses']:
            print(f"Hotspot accesses found: {len(bank_info['hotspot_accesses'])}")
    
    # CPU SIMULATOR: merge execution-traced addresses (done AFTER bank re-detection
    # so bank scheme is determined from static analysis only, preventing misdetection)
    print("\n=== CPU Simulator: Deep Execution Tracing ===")
    print("  Performing exhaustive static analysis (seeding every ROM byte as a")
    print("  potential entry point). This gives near-100% code coverage and is")
    print("  the most accurate disassembly possible from static analysis alone.")
    _sim_dispatch_targets: Set[int] = set()
    try:
        _sim_offsets, _sim_dispatch_targets = simulate_rom(rom, deep=True)
        _rsz = len(rom)
        _bsz = bank_info['bank_size'] if bank_info else _rsz

        # Build a set of ALL bytes (instruction + operands) confirmed as code by
        # the static flow analysis.  These are the bytes we TRUST 100%.
        _static_code_bytes: Set[int] = set()
        for _o in code_addresses:
            if 0 <= _o < _rsz and rom[_o] in OPCODES:
                _, _s, _ = OPCODES[rom[_o]]
                for _b in range(_s):
                    _static_code_bytes.add(_o + _b)

        _nadd = 0
        for _o in sorted(_sim_offsets):
            if not (0 <= _o < _rsz): continue
            _op = rom[_o]
            if _op not in OPCODES: continue
            _mn, _sz, _md = OPCODES[_op]
            # Don't split existing instructions (would corrupt the operand bytes)
            _ok = all((_o+_b) not in _static_code_bytes for _b in range(1, _sz))
            if not _ok: continue
            if _md == 'relative' and _o + 1 < _rsz:
                _r = rom[_o + 1]; _r = _r - 256 if _r >= 128 else _r
                _t = _o + 2 + _r
                if _o // _bsz != _t // _bsz or _t < 0 or _t >= _rsz: continue
            if _o not in code_addresses: _nadd += 1
            code_addresses.add(_o)
        print(f"  Simulation found {len(_sim_offsets)} executed offsets")
        print(f"  Added {_nadd} new offsets not found by static analysis")
        print(f"  Found {len(_sim_dispatch_targets)} indirect dispatch table targets")
    except Exception as _e:
        print(f"  CPU simulator error (ignored): {_e}")

    # Analyze code patterns
    print("\n=== Pattern Analysis ===")
    pattern_recognizer = PatternRecognizer()
    patterns = pattern_recognizer.analyze_patterns(rom, code_addresses, base_addr)
    
    print(f"Found {len(patterns)} code patterns:")
    for pc, pattern in sorted(patterns.items()):
        addr = base_addr + pc
        print(f"  ${addr:04X}: {pattern['type']} - {pattern['description']}")
    
    # Build a map of code sections and their descriptions

    # This will be used for cross-references
    code_section_map = {}
    pc = 0
    in_code = False
    code_start = 0
    
    while pc < rom_size:
        is_code = pc in code_addresses
        
        if is_code and not in_code:
            # Starting a new code section
            code_start = pc
            in_code = True
        elif not is_code and in_code:
            # Ending a code section
            description = analyze_code_section(rom, code_start, pc, code_addresses, base_addr)
            code_section_map[base_addr + code_start] = description
            in_code = False
        
        pc += 1
    
    # Handle last section if it's code
    if in_code:
        description = analyze_code_section(rom, code_start, rom_size, code_addresses, base_addr)
        code_section_map[base_addr + code_start] = description
    
    # Generate labels for jump/branch targets (only if enabled)
    labels = {}
    if SHOW_LABELS:
        subroutines = set()  # Track JSR targets
        jump_targets = set()  # Track JMP targets
        branch_targets = set()  # Track branch targets
        
        # First pass: collect all targets
        pc = 0
        while pc < rom_size:
            if pc in code_addresses:
                opcode = rom[pc]
                if opcode in OPCODES:
                    mnemonic, size, mode = OPCODES[opcode]
                    
                    if mnemonic == 'JSR' and size == 3 and pc + 2 < rom_size:
                        target_addr = read_word(rom, pc + 1)
                        subroutines.add(target_addr)
                    elif mnemonic == 'JMP' and mode == 'absolute' and size == 3 and pc + 2 < rom_size:
                        target_addr = read_word(rom, pc + 1)
                        jump_targets.add(target_addr)
                    elif mnemonic in ['BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ'] and pc + 2 < rom_size:
                        offset = rom[pc + 1]
                        if offset >= 128:
                            offset = offset - 256
                        # Calculate target ROM offset
                        target_pc = pc + 2 + offset
                        # Convert to bank-aware address
                        if 0 <= target_pc < rom_size:
                            _, target_addr = get_bank_info_for_offset(target_pc, rom_size, bank_scheme, 
                                                                      bank_info['banks'] if bank_info else 1,
                                                                      bank_info['bank_size'] if bank_info else rom_size)
                            branch_targets.add(target_addr)
                    
                    pc += size
                else:
                    pc += 1
            else:
                pc += 1
        
        # Helper function to check if a code block ends with RTS/RTI
        def ends_with_return(start_addr):
            """Check if code starting at start_addr eventually ends with RTS or RTI"""
            if start_addr < base_addr or start_addr >= base_addr + rom_size:
                return False
            
            pc = start_addr - base_addr
            visited = set()
            max_instructions = 100  # Prevent infinite loops
            
            for _ in range(max_instructions):
                if pc in visited or pc < 0 or pc >= rom_size:
                    return False
                if pc not in code_addresses:
                    return False
                    
                visited.add(pc)
                opcode = rom[pc]
                
                if opcode not in OPCODES:
                    return False
                
                mnemonic, size, mode = OPCODES[opcode]
                
                # Found a return instruction
                if mnemonic in ['RTS', 'RTI']:
                    return True
                
                # Unconditional jump or branch - stop following
                if mnemonic == 'JMP':
                    return False
                
                # Continue to next instruction
                pc += size
            
            return False
        
        # Helper: check if a memory address maps to a code address in this ROM.
        # Build the valid address ranges from get_bank_info_for_offset so that
        # unmapped gaps (e.g. $E000-$EFFF for F8) are correctly excluded.
        _valid_mem_addrs = None
        def _build_valid_addrs():
            nonlocal _valid_mem_addrs
            valid = set()
            for off in range(rom_size):
                _, ma = get_bank_info_for_offset(off, rom_size, bank_scheme,
                                                 bank_info['banks'] if bank_info else 1,
                                                 bank_info['bank_size'] if bank_info else rom_size)
                valid.add(ma)
            _valid_mem_addrs = valid

        def is_valid_rom_addr(mem_addr):
            """Return True iff mem_addr is within this ROM's mapped address space."""
            nonlocal _valid_mem_addrs
            if mem_addr < 0xC000 or mem_addr >= 0x10000:
                return False
            if _valid_mem_addrs is None:
                _build_valid_addrs()
            return mem_addr in _valid_mem_addrs
        
        def addr_to_rom_offset(mem_addr):
            """Convert memory address back to ROM offset (approximate, first bank match).
            Uses the same bank address formula as get_bank_info_for_offset().
            """
            if not bank_scheme:
                return mem_addr - base_addr
            # Banked: try each bank using the same address formula
            bk_count = bank_info['banks'] if bank_info else 1
            bk_size  = bank_info['bank_size'] if bank_info else rom_size
            # Last bank always at $F000-$FFFF
            last_bank_mem_start = 0x10000 - bk_size  # e.g. $F000 for 4K banks
            if mem_addr >= last_bank_mem_start:
                return (bk_count - 1) * bk_size + (mem_addr - last_bank_mem_start)
            # Earlier banks: use formula distance_from_last -> 0xE000 - dist*0x1000
            for bk in range(bk_count - 1):
                dist = (bk_count - 1) - bk
                bk_mem_start = 0xE000 - dist * 0x1000
                bk_mem_end   = bk_mem_start + bk_size
                if bk_mem_start <= mem_addr < bk_mem_end:
                    return bk * bk_size + (mem_addr - bk_mem_start)
            # Fallback
            return mem_addr - base_addr
        
        # Generate generic labels with smart subroutine detection.
        # Only create a label if:
        #   1. The target address is within valid ROM address space.
        #   2. The target ROM offset is in code_addresses (the disassembler identified
        #      that byte as the start of an instruction). If it's data, emitting a label
        #      there is impossible because the output has no label line for data regions;
        #      the assembler must just use the raw hex address.
        for addr in sorted(subroutines):
            if not is_valid_rom_addr(addr):
                continue  # e.g. JSR $0D29 – RAM/TIA target, emit raw hex
            rom_off = addr_to_rom_offset(addr)
            if 0 <= rom_off < rom_size and rom_off in code_addresses:
                labels[addr] = f'Subroutine_{addr:04X}'
            # else: target lands in data region – no label; format_operand will use $XXXX
        
        # Add indirect dispatch table targets to jump_targets so they get labels.
        # These are addresses reached via JMP ($zp) where the pointer is loaded
        # from split lo/hi ROM tables — they are real code entry points but no
        # JSR or JMP absolute instruction directly references them.
        for _dt in _sim_dispatch_targets:
            jump_targets.add(_dt)

        for addr in sorted(jump_targets):
            if addr not in labels:
                if not is_valid_rom_addr(addr):
                    continue
                rom_off = addr_to_rom_offset(addr)
                if 0 <= rom_off < rom_size and rom_off in code_addresses:
                    labels[addr] = f'Jump_{addr:04X}'
        
        # Branch targets: always emit a label (branches are PC-relative within a single
        # bank, so the target is always in the same bank and always in code).
        # Do NOT filter branch_targets by is_valid_rom_addr or code_addresses – the
        # branch offset calculation in format_operand already converts offsets correctly,
        # and the target byte MUST be a valid instruction start (otherwise the CPU would
        # crash, and the disassembler would have already classified it as code).
        for addr in sorted(branch_targets):
            if addr not in labels:
                # Check if this branch target is actually a subroutine (ends with RTS)
                if ends_with_return(addr):
                    labels[addr] = f'Subroutine_{addr:04X}'
                else:
                    labels[addr] = f'Branch_{addr:04X}'
        
        # NEW: Generate labels for ROM data based on TIA register usage.
        # For each address in tia_data_map we need to find the DATA BLOCK that
        # contains it (the block that get_data_region_comment will classify) and
        # label its start. We use the same majority-vote logic as the comment
        # generator so the label always matches the header description.
        if tia_data_map:
            _grp_regs  = {'GRP0', 'GRP1'}
            _pf_regs   = {'PF0', 'PF1', 'PF2'}
            _col_regs  = {'COLUP0', 'COLUP1', 'COLUPF', 'COLUBK'}
            _aud_regs  = {'AUDC0', 'AUDC1', 'AUDF0', 'AUDF1', 'AUDV0', 'AUDV1'}
            _pos_regs  = {'RESP0', 'RESP1', 'RESM0', 'RESM1', 'RESBL'}
            _mot_regs  = {'HMP0', 'HMP1', 'HMM0', 'HMM1', 'HMBL'}

            def _tia_label_for_block(block_start_pc, block_end_pc):
                """Return a label prefix for the data block using majority-vote."""
                cat = {'grp': 0, 'pf': 0, 'col': 0, 'aud': 0, 'pos': 0, 'mot': 0, 'other': 0}
                tia_hits = 0
                block_size = block_end_pc - block_start_pc
                for off in range(block_start_pc, block_end_pc):
                    mem = base_addr + off
                    if mem in tia_data_map:
                        regs = set(tia_data_map[mem])
                        tia_hits += 1
                        if regs & _grp_regs:    cat['grp'] += 1
                        elif regs & _pf_regs:   cat['pf']  += 1
                        elif regs & _col_regs:  cat['col'] += 1
                        elif regs & _aud_regs:  cat['aud'] += 1
                        elif regs & _pos_regs:  cat['pos'] += 1
                        elif regs & _mot_regs:  cat['mot'] += 1
                        else:                   cat['other'] += 1
                dominant = max(cat, key=cat.get)
                tia_frac = tia_hits / block_size if block_size > 0 else 0
                # Same sparseness rule as get_data_region_comment
                if dominant not in ('grp', 'pf') and tia_frac < 0.20 and block_size >= 24:
                    return None  # too sparse, let heuristic name it
                return {'grp': 'GraphicsData', 'pf': 'GraphicsData',
                        'col': 'ColorData',    'aud': 'AudioData',
                        'pos': 'PositionData', 'mot': 'MotionData',
                        'other': 'TIAData'}.get(dominant, 'TIAData')

            # Walk the ROM finding data-block boundaries, then label blocks that
            # contain TIA-mapped addresses using the majority-vote prefix.
            print(f"\n=== TIA Data Labeling ===")
            _pc = 0
            while _pc < rom_size:
                if _pc in code_addresses:
                    _pc += 1
                    continue
                # Found start of a data block
                _blk_start = _pc
                while _pc < rom_size and _pc not in code_addresses:
                    _pc += 1
                _blk_end = _pc
                _blk_addr = base_addr + _blk_start  # memory address of block start

                # Only label if the block start address is in labels (already labelled
                # by a TIA key) OR if any byte in the block is in tia_data_map and
                # the block start has no label yet.
                has_tia_hit = any((base_addr + off) in tia_data_map
                                  for off in range(_blk_start, _blk_end))
                if has_tia_hit and _blk_addr not in labels:
                    prefix = _tia_label_for_block(_blk_start, _blk_end)
                    if prefix:
                        labels[_blk_addr] = f'{prefix}_{_blk_addr:04X}'
                        print(f"  Created label: {labels[_blk_addr]}")
        
        # REMOVED: These blocks were creating labels for EVERY code section, pattern, and data section
        # Labels should ONLY be created for actual jump/branch/call targets (JSR, JMP, branches)
        # 
        # # Also add labels for code section starts (for better organization)
        # # This makes sections with comment headers properly indented
        # for section_addr in code_section_map.keys():
        #     if section_addr not in labels:
        #         labels[section_addr] = f'Section_{section_addr:04X}'
        # 
        # # Add labels for detected code patterns (like TIMER SETUP, VBLANK, etc.)
        # # This makes pattern-identified code sections properly indented
        # for pc, pattern in patterns.items():
        #     pattern_addr = base_addr + pc
        #     if pattern_addr not in labels:
        #         # Use pattern type as part of label name
        #         pattern_type = pattern['type'].replace('_', '').title().replace(' ', '')
        #         labels[pattern_addr] = f'{pattern_type}_{pattern_addr:04X}'
        # 
        # # Add labels for data section starts (for consistency with code sections)
        # # This ensures data sections are also properly indented
        # pc = 0
        # in_data = False
        # while pc < rom_size:
        #     is_code = pc in code_addresses
        #     if not is_code and not in_data:
        #         # Starting a new data section
        #         data_addr = base_addr + pc
        #         if data_addr not in labels:
        #             labels[data_addr] = f'Data_{data_addr:04X}'
        #         in_data = True
        #     elif is_code and in_data:
        #         in_data = False
        #     pc += 1
    
    # Generate cross-references if enabled
    xref = None
    if SHOW_XREFS:
        print("\n=== Cross-Reference Analysis ===")
        xref = CrossReferencer()
        xref.analyze_references(rom, code_addresses, base_addr, labels)

        # Register indirect dispatch targets from the CPU simulator so the
        # xref summary can show "Dispatched from $XXXX via JMP ($zp)".
        # We need to find the dispatch site (the JMP ($zp) instruction address)
        # for each group of targets.  We do this by scanning code_addresses for
        # JMP indirect opcodes (0x6C) and checking if any of their targets are
        # in _sim_dispatch_targets.
        if _sim_dispatch_targets:
            # Build a mapping: dispatch_site_cpu_addr -> set of targets
            # by scanning the ROM for JMP ($zp) = 0x6C in confirmed code
            _bk_count = bank_info['banks'] if bank_info else 1
            _bk_size  = bank_info['bank_size'] if bank_info else rom_size
            _dispatch_sites = {}  # dispatch_cpu_addr -> set(target_cpu_addrs)
            
            for _jmp_off in sorted(code_addresses):
                if rom[_jmp_off] != 0x6C:  # JMP indirect
                    continue
                if _jmp_off + 2 >= len(rom):
                    continue
                if rom[_jmp_off + 2] != 0x00:  # must be zero-page form
                    continue
                # This is a confirmed JMP ($zp) in code
                _, _jmp_cpu = get_bank_info_for_offset(_jmp_off, len(rom), bank_scheme,
                                                        _bk_count, _bk_size)
                # Associate ALL dispatch targets with this site
                # (we can't know which ones this specific JMP dispatches to
                #  without full register tracking, so we associate all of them
                #  with this dispatch site if targets exist)
                _dispatch_sites[_jmp_cpu] = _sim_dispatch_targets

            for _site_addr, _targets in _dispatch_sites.items():
                xref.register_dispatch_targets(_targets, _site_addr)
            
            if _dispatch_sites:
                print(f"  Registered {len(_sim_dispatch_targets)} dispatch targets "
                      f"from {len(_dispatch_sites)} indirect JMP site(s)")
        
        total_subs = len(set(xref.calls.keys()) | set(xref.called_by.keys()))
        total_calls = sum(xref.call_counts.values())
        print(f"Analyzed {total_subs} subroutines")
        print(f"Found {total_calls} subroutine calls")
        
        # Find most called subroutine
        if xref.called_by:
            most_called = max(xref.called_by.items(), key=lambda x: len(x[1]))
            most_called_addr, callers = most_called
            most_called_name = labels.get(most_called_addr, f"${most_called_addr:04X}")
            print(f"Most called: {most_called_name} ({len(callers)} callers)")
    
    # Detect illegal opcodes used in the ROM
    ILLEGAL_OPCODES = {
        'SLO', 'RLA', 'SRE', 'RRA', 'SAX', 'LAX', 'DCP', 'ISC',
        'ANC', 'ALR', 'ARR', 'XAA', 'AHX', 'TAS', 'SHY', 'SHX', 'LAS', 'AXS'
    }
    
    illegal_opcodes_found = set()  # Store mnemonic names
    illegal_opcode_count = 0
    
    # Scan through code to find illegal opcodes (only at instruction boundaries)
    pc = 0
    while pc < rom_size:
        if pc not in code_addresses:
            pc += 1
            continue
            
        opcode = rom[pc]
        if opcode not in OPCODES:
            pc += 1
            continue
        
        mnemonic, size, mode = OPCODES[opcode]
        if mnemonic in ILLEGAL_OPCODES:
            illegal_opcodes_found.add(mnemonic)  # Store mnemonic name
            illegal_opcode_count += 1
        
        pc += size
    
    # Calculate statistics
    code_byte_count = len(code_addresses)
    data_byte_count = rom_size - code_byte_count
    code_percent = (code_byte_count / rom_size * 100) if rom_size > 0 else 0
    data_percent = (data_byte_count / rom_size * 100) if rom_size > 0 else 0
    
    # Count sections
    code_section_count = len(code_section_map)
    data_section_count = 0
    pc = 0
    in_data = False
    while pc < rom_size:
        is_code = pc in code_addresses
        if not is_code and not in_data:
            data_section_count += 1
            in_data = True
        elif is_code and in_data:
            in_data = False
        pc += 1
    
    with open(output_path, 'w', encoding='utf-8') as out:
        out.write(f";==============================================================================\n")
        out.write(f"; Atari 2600 Disassembly\n")
        out.write(f"; Processor: 6507 (cost-reduced 6502)\n")
        out.write(f";\n")
        out.write(f"; ROM: {rom_name}\n")
        out.write(f"; Size: {rom_size} bytes\n")
        out.write(f"; Base Address: ${base_addr:04X}\n")
        out.write(f";\n")
        
        # Add cartridge type info (always show, even for 4K)
        if bank_scheme:
            bank_info = bank_switcher.get_bank_info()
            out.write(f"; Bank Switching: {bank_info['description']}\n")
            out.write(f";   Banks: {bank_info['banks']}\n")
            out.write(f";   Bank Size: {bank_info['bank_size']} bytes (${bank_info['bank_size']:04X})\n")
            
            # Add hotspot information if available
            if bank_info['hotspots']:
                out.write(f";\n")
                out.write(f";   Hotspot Addresses:\n")
                for hotspot, bank in sorted(bank_info['hotspots'].items()):
                    access_count = bank_info['hotspot_accesses'].get(hotspot, 0)
                    if access_count > 0:
                        out.write(f";     ${hotspot:04X} -> Bank {bank} (accessed {access_count} times)\n")
                    else:
                        out.write(f";     ${hotspot:04X} -> Bank {bank}\n")
        else:
            # Non-banked ROM: describe the actual size
            if rom_size <= 2048:
                out.write(f"; Bank Switching: 2K (2K Atari (no banking))\n")
            else:
                out.write(f"; Bank Switching: 4K (4K Atari (no banking))\n")
        out.write(f";\n")
        
        out.write(f"; Statistics:\n")
        out.write(f";   Code bytes: {code_byte_count} ({code_percent:.1f}%)\n")
        out.write(f";   Data bytes: {data_byte_count} ({data_percent:.1f}%)\n")
        out.write(f";   Code sections: {code_section_count}\n")
        out.write(f";   Data sections: {data_section_count}\n")
        out.write(f";\n")
        
        # Report illegal opcode usage
        if illegal_opcodes_found:
            out.write(f"; Illegal/Undocumented Opcodes: YES ({len(illegal_opcodes_found)} types, {illegal_opcode_count} total)\n")
            out.write(f";   Used: {', '.join(sorted(illegal_opcodes_found))}\n")
        else:
            out.write(f"; Illegal/Undocumented Opcodes: NO (uses only standard 6507 opcodes)\n")
        
        out.write(f";\n;==============================================================================\n\n")
        out.write(f"processor 6507\n")
        
        # Output Atari 2600 hardware register definitions (organized by category)
        
        symbols = get_all_symbols()
        align_column = calculate_alignment_column()
        
        # Group symbols by category
        categories = {}
        for name, addr, desc, category in symbols:
            if category not in categories:
                categories[category] = []
            categories[category].append((name, addr, desc))
        
        # Category headers (single line format)
        category_headers = {
            'COLLISION': 'Collision Detection (Read): Sprite collision detection registers',
            'INPUT': 'Input Ports (Read): Controller and paddle input registers',
            'SYNC': 'Sync and Timing: Vertical/horizontal sync and blanking control',
            'GRAPHICS': 'Graphics Registers: Players, missiles, ball, and playfield control',
            'COLOR': 'Color Registers: Colors for players, playfield, and background',
            'AUDIO': 'Audio Registers: Sound generation (2 channels)',
            'MOTION': 'Horizontal Motion: Sprite horizontal movement control',
            'RIOT': 'RIOT Chip (I/O and Timer): RAM-I/O-Timer chip registers',
        }
        
        # Output each category
        category_order = ['COLLISION', 'INPUT', 'SYNC', 'GRAPHICS', 'COLOR', 'AUDIO', 'MOTION', 'RIOT']
        
        for category in category_order:
            if category in categories:
                header_text = category_headers[category]
                out.write(f"\n; {header_text}\n")
                
                for name, addr, desc in categories[category]:
                    symbol_line = f"{name:<18} = ${addr:04X}"
                    if desc and SHOW_COMMENTS:
                        padded_line = f"{symbol_line:<{align_column}}"
                        out.write(f"{padded_line} ; {desc}\n")
                    else:
                        out.write(f"{symbol_line}\n")
        
        # Output RAM variable definitions
        if variables:
            out.write(f"\n; RAM Variables ($80-$FF)\n")
            for addr, var_info in variables:
                var_name = var_info['name']
                var_type = var_info['type']
                reads = var_info['reads']
                writes = var_info['writes']
                
                # Add comment describing the variable
                type_desc = {
                    'pointer': 'Pointer (low byte)',
                    'pointer_high': 'Pointer (high byte)',
                    'array': 'Array/indexed access',
                    'constant': 'Read-only constant',
                    'temp': 'Temporary variable',
                    'flag': 'Flag/status variable',
                    'var': 'General variable'
                }.get(var_type, 'Variable')
                
                # Format with aligned name, =, value, and comment
                # Use same dynamic alignment as code and TIA symbols
                var_line = f"{var_name:<18} = ${addr:02X}"
                if SHOW_COMMENTS:
                    # Pad the var line to align_column, then add space and comment
                    # This ensures the semicolon is always at position align_column
                    padded_line = f"{var_line:<{align_column}}"
                    out.write(f"{padded_line} ; {type_desc} (R:{reads} W:{writes})\n")
                else:
                    out.write(f"{var_line}\n")
        
        # Determine bank information for output
        if bank_scheme and bank_info:
            output_bank_count = bank_info['banks']
            output_bank_size = bank_info['bank_size']
        else:
            output_bank_count = 1
            output_bank_size = rom_size
        
        out.write(f"\n; ============================================================================\n")
        if bank_scheme:
            out.write(f"; CODE SECTION - Multi-bank ROM\n")
        else:
            out.write(f"; CODE SECTION - Program starts at ${base_addr:04X}\n")
        out.write(f"; ============================================================================\n")
        
        pc = 0
        in_data_block = False
        in_code_block = False
        data_start = 0
        code_start = 0
        under_label = False  # Track if we're under a label for indentation
        current_bank = -1  # Track which bank we're currently outputting
        
        while pc < rom_size:
            # Get bank number and memory address for this offset
            bank_num, mem_addr = get_bank_info_for_offset(pc, rom_size, bank_scheme, output_bank_count, output_bank_size)
            
            # Check if we're entering a new bank
            if bank_num != current_bank:
                current_bank = bank_num
                
                # Close any pending data row before switching banks (prevents trailing comma)
                if in_data_block:
                    # Check if we're mid-row (haven't just written a newline)
                    # data_start tracks the start of this data block; (pc - data_start) % 16
                    # tells us how many bytes into the current row we are. If > 0 we're mid-row.
                    if (pc - data_start) % 16 != 0:
                        out.write('\n')
                
                # Output bank header
                if bank_scheme:
                    out.write(f"\n; ============================================================================\n")
                    out.write(f"; BANK {bank_num}\n")
                    out.write(f"; ROM Offset: ${pc:04X}-${min(pc + output_bank_size - 1, rom_size - 1):04X}\n")
                    out.write(f"; Memory Map: ${mem_addr:04X}-${mem_addr + output_bank_size - 1:04X}\n")
                    out.write(f"; ============================================================================\n")
                
                # Output ORG directive for this bank.
                # Use the canonical start address of this bank (bank_num * bank_size
                # converted to memory address), NOT the address of the current byte
                # (which may be mid-instruction if the previous bank's last instruction
                # crossed the bank boundary).
                _, bank_org = get_bank_info_for_offset(
                    bank_num * output_bank_size, rom_size,
                    bank_scheme, output_bank_count, output_bank_size
                )
                out.write(f"        ORG ${bank_org:04X}\n\n")
                
                # Reset block tracking when entering new bank
                in_data_block = False
                in_code_block = False
                under_label = False
            
            addr = mem_addr
            
            # Check if this is code or data
            is_code = pc in code_addresses
            
            if is_code:
                # Flush any pending data block
                if in_data_block:
                    in_data_block = False
                    under_label = False  # Reset when leaving data
                    # Always write a blank line when transitioning from data to code.
                    # If no label follows, also write a separator comment so the reader
                    # can clearly see where data ends and code begins (especially important
                    # when the code starts with illegal opcodes emitted as .byte lines,
                    # which look visually identical to data .byte lines).
                    out.write('\n')
                    if addr not in labels:
                        out.write(f'; ----------- CODE ${addr:04X} -----------\n')
                
                # Check if we're starting a new code section
                if not in_code_block:
                    in_code_block = True
                    code_start = pc
                    under_label = False  # Reset when starting new code section
                    # Don't output section comment here - it will be output at labels instead
                
                # Check for pattern comments
                pattern_comment = pattern_recognizer.get_pattern_comment(pc, patterns)
                if pattern_comment:
                    out.write(pattern_comment)
                    # Don't reset indentation - pattern comments are just informational
                
                # Check for section comments
                section_comment = get_section_comment(addr)
                if section_comment:
                    out.write(section_comment)
                    # Don't reset indentation - section comments are just informational
                
                # Check if we need a label here
                has_label = addr in labels
                if has_label:
                    label_name = labels[addr]
                    
                    # Only generate section headers for ACTUAL JSR targets (not branch targets that happen to end with RTS)
                    # Check if this address is in the subroutines set (actual JSR targets)
                    is_jsr_target = addr in subroutines
                    
                    if is_jsr_target:
                        # Calculate the size of this subroutine by scanning forward to RTS/RTI/JMP
                        scan_pc = pc
                        section_size = 0
                        while scan_pc < rom_size and scan_pc in code_addresses:
                            if scan_pc not in code_addresses:
                                break
                            scan_opcode = rom[scan_pc]
                            if scan_opcode not in OPCODES:
                                break
                            scan_mnemonic, scan_size, scan_mode = OPCODES[scan_opcode]
                            section_size += scan_size
                            scan_pc += scan_size
                            # Stop at RTS, RTI, or unconditional JMP
                            if scan_mnemonic in ['RTS', 'RTI'] or (scan_mnemonic == 'JMP' and scan_mode == 'absolute'):
                                break
                        
                        # Generate section header with accurate size
                        code_comment = get_code_section_comment(rom, pc, pc + section_size, code_addresses, base_addr, code_section_map, show_xrefs=SHOW_XREFS, xref=xref, labels=labels)
                        out.write(code_comment + '\n')
                    
                    # Output the label (with blank line before it for readability)
                    out.write(f'\n{label_name}:\n')
                    
                    under_label = True  # Start indenting after this label
                
                opcode = rom[pc]
                if opcode in OPCODES:
                    mnemonic, size, mode = OPCODES[opcode]
                    
                    if pc + size > rom_size:
                        # Incomplete instruction
                        out.write(f'${addr:04X}: {rom[pc]:02X}       .byte ${rom[pc]:02X}\n')
                        pc += 1
                        continue
                    
                    # Check if this instruction crosses a bank boundary.
                    # If any operand byte is in a different bank than the opcode byte,
                    # emit only the opcode byte as .byte and let the bank switch handle
                    # the rest on the next iteration.
                    if size > 1 and bank_scheme:
                        last_byte_bank, _ = get_bank_info_for_offset(
                            pc + size - 1, rom_size, bank_scheme,
                            output_bank_count, output_bank_size
                        )
                        if last_byte_bank != bank_num:
                            indent = '  ' if under_label else ''
                            if SHOW_ADDRESSES:
                                out.write(f'{indent}${addr:04X}: .byte ${rom[pc]:02X}  ; {mnemonic} crosses bank boundary\n')
                            else:
                                out.write(f'{indent}.byte ${rom[pc]:02X}  ; {mnemonic} crosses bank boundary\n')
                            pc += 1
                            continue
                    
                    # Check if any operand byte (pc+1 .. pc+size-1) has a label.
                    # This happens when a branch target lands inside a multi-byte instruction.
                    # In that case, emit the opcode byte as .byte so the label can be
                    # placed at the correct position on the next iteration.
                    if size > 1:
                        operand_has_label = False
                        for op_off in range(1, size):
                            _, op_mem_addr = get_bank_info_for_offset(
                                pc + op_off, rom_size, bank_scheme,
                                output_bank_count, output_bank_size
                            )
                            if op_mem_addr in labels:
                                operand_has_label = True
                                break
                        if operand_has_label:
                            # Emit just the opcode byte as .byte and re-visit operand bytes
                            indent = '  ' if under_label else ''
                            if SHOW_ADDRESSES:
                                out.write(f'{indent}${addr:04X}: .byte ${rom[pc]:02X}  ; split: label inside operand\n')
                            else:
                                out.write(f'{indent}.byte ${rom[pc]:02X}  ; split: label inside operand\n')
                            pc += 1
                            continue
                    
                    operand_bytes = rom[pc+1:pc+size]

                    # Illegal/undocumented opcodes: emit as .byte for assembler compatibility
                    # but include a disassembled form in the comment so humans can read it.
                    # Format:  .byte $BF,$88,$D5          ; LAX $D588,Y  (illegal opcode)
                    # The semicolon aligns at the same column as all other instruction comments.
                    if opcode not in OFFICIAL_6502_OPCODES:
                        indent = '  ' if under_label else ''
                        byte_args = ','.join(f'${rom[pc+i]:02X}' for i in range(size))
                        # Build the human-readable disassembly for the comment
                        operand_str_ill = format_operand(mode, operand_bytes, addr, labels, var_tracker,
                                                         rom_offset=pc, rom_size=rom_size, bank_scheme=bank_scheme,
                                                         bank_count=output_bank_count, bank_size=output_bank_size)
                        ill_disasm = f'{mnemonic} {operand_str_ill}'.strip() if operand_str_ill else mnemonic
                        if SHOW_ADDRESSES:
                            raw_line = f'{indent}${addr:04X}: .byte {byte_args}'
                        else:
                            raw_line = f'{indent}.byte {byte_args}'
                        align_col = calculate_alignment_column()
                        # Build comment parts same as legal instructions
                        ill_comment_parts = []
                        if SHOW_CYCLES:
                            ill_cyc = format_cycles(opcode, mode)
                            if ill_cyc:
                                ill_comment_parts.append(f'[{ill_cyc:>6}]')
                        if SHOW_FLAGS:
                            ill_flags = format_flags_comment(mnemonic)
                            if ill_flags:
                                ill_comment_parts.append(ill_flags)
                        if SHOW_OPERATIONS:
                            ill_ops = format_operation_comment(mnemonic)
                            if ill_ops:
                                ill_comment_parts.append(ill_ops)
                        ill_comment_parts.append(f'{ill_disasm}  (illegal opcode)')
                        ill_comment = ' | '.join(ill_comment_parts)
                        out.write(f'{raw_line:<{align_col}} ; {ill_comment}\n')
                        pc += size
                        continue

                    # Pass bank context for bank-aware branch target calculation
                    operand_str = format_operand(mode, operand_bytes, addr, labels, var_tracker,
                                                 rom_offset=pc, rom_size=rom_size, bank_scheme=bank_scheme,
                                                 bank_count=output_bank_count, bank_size=output_bank_size)
                    
                    hex_bytes = ' '.join(f'{rom[pc+i]:02X}' for i in range(size))
                    hex_bytes = f'{hex_bytes:<8}'
                    
                    # Get intelligent comment for this instruction
                    comment = get_instruction_comment(mnemonic, operand_str, addr) if SHOW_COMMENTS else ""
                    
                    # Add xref comment for JSR instructions if enabled
                    if SHOW_XREFS and xref and mnemonic == 'JSR' and size == 3:
                        target_addr = operand_bytes[0] | (operand_bytes[1] << 8)
                        # Get the target name from labels or format as address
                        target_name = labels.get(target_addr, f"${target_addr:04X}")
                        xref_comment = f"Calls: {target_name}"
                        if comment:
                            comment = f"{comment} | {xref_comment}"
                        else:
                            comment = xref_comment
                    
                    # Check if this instruction accesses a bank switching hotspot
                    if bank_scheme and mode == 'absolute' and size == 3:
                        target_addr = operand_bytes[0] | (operand_bytes[1] << 8)
                        is_hotspot, bank_num = bank_switcher.is_hotspot_address(target_addr)
                        if is_hotspot:
                            hotspot_comment = f"SWITCH TO BANK {bank_num}"
                            if comment:
                                comment = f"{comment} | {hotspot_comment}"
                            else:
                                comment = hotspot_comment
                    
                    # Get cycle count if enabled
                    cycles = format_cycles(opcode, mode) if SHOW_CYCLES else ""
                    
                    # Build the line based on flags
                    line_parts = []
                    
                    # Add indentation if we're under a label
                    indent = '  ' if under_label else ''
                    
                    if SHOW_ADDRESSES:
                        line_parts.append(f'${addr:04X}:')
                    if SHOW_HEX:
                        line_parts.append(hex_bytes)
                    line_parts.append(f'{mnemonic:<6}')
                    if operand_str:
                        line_parts.append(operand_str)
                    
                    line = indent + ' '.join(line_parts)
                    
                    # Add comment with optional cycle count, flags, and operations
                    if SHOW_COMMENTS or SHOW_CYCLES or SHOW_FLAGS or SHOW_OPERATIONS:
                        comment_parts = []
                        
                        # Add cycle count first if enabled
                        if SHOW_CYCLES and cycles:
                            comment_parts.append(f'[{cycles:>6}]')
                        
                        # Add processor flags if enabled
                        if SHOW_FLAGS:
                            flags_comment = format_flags_comment(mnemonic)
                            if flags_comment:
                                comment_parts.append(flags_comment)
                        
                        # Add operation description if enabled
                        if SHOW_OPERATIONS:
                            operation = format_operation_comment(mnemonic)
                            if operation:
                                comment_parts.append(operation)
                        
                        # Add instruction comment if enabled
                        if comment and SHOW_COMMENTS:
                            comment_parts.append(comment)
                        
                        # Combine comment parts
                        if comment_parts:
                            combined_comment = " | ".join(comment_parts)
                            # Use centralized alignment calculation
                            align_column = calculate_alignment_column()
                            line = f'{line:<{align_column}} ; {combined_comment}'
                    
                    out.write(line + '\n')
                    
                    pc += size
                else:
                    out.write(f'${addr:04X}: {rom[pc]:02X}       .byte ${rom[pc]:02X}  ; Invalid opcode\n')
                    pc += 1
            else:
                # Data region
                if in_code_block:
                    in_code_block = False
                
                if not in_data_block:
                    # Find the end of this data region
                    data_end = pc + 1
                    while data_end < rom_size and data_end not in code_addresses:
                        data_end += 1
                    
                    # Analyze and output intelligent comment (pass var_tracker for smarter visualization)
                    # Also pass tia_data_map so the header can reflect actual TIA register usage
                    data_comment, visualization_data = get_data_region_comment(rom, pc, data_end, code_addresses, base_addr, code_section_map, show_xrefs=SHOW_XREFS, var_tracker=var_tracker, tia_data_map=tia_data_map)
                    out.write(data_comment + '\n')
                    
                    # Check if this data section has a label
                    if addr in labels:
                        out.write(f'\n{labels[addr]}:\n')
                        under_label = True  # Start indenting data under this label
                    else:
                        under_label = False  # No label, no indentation
                    
                    in_data_block = True
                    data_start = pc
                    data_visualization = visualization_data  # Store for later
                    data_code_prefix_end = pc  # no prefix suppression (handled by simulator)
                else:
                    # Mid data block: check if this byte has a label (e.g. branch target
                    # whose address fell inside a multi-byte instruction that was split).
                    if addr in labels:
                        # Close the current data row first (if mid-row)
                        if (pc - data_start) % 16 != 0:
                            out.write('\n')
                        out.write(f'\n{labels[addr]}:\n')
                        under_label = True
                        # Reset data_start so the row counter restarts after the label
                        data_start = pc

                
                # Check if we should visualize this data inline
                is_graphics = VISUALIZE_DATA and data_visualization is not None
                
                # Add indentation if we're under a label
                indent = '  ' if under_label else ''
                
                # Check if this address has TIA register usage information.
                # Only show "feeds X" for DIRECT (non-indexed) loads — indexed
                # loads are marked with a tilde prefix (~) and suppressed here.
                tia_comment = ""
                if addr in tia_data_map:
                    tia_regs = tia_data_map[addr]
                    # Filter out tilde-prefixed (indexed) markers
                    direct_regs = [r for r in tia_regs if not r.startswith('~')]
                    if direct_regs:
                        tia_comment = f"feeds {', '.join(direct_regs)}"
                
                if is_graphics:
                    # Output one byte per line with visual comment
                    from analyzers import byte_to_ascii_art
                    byte_val = rom[pc]

                    # Suppress pixel art for bytes in alternating-value sequences.
                    # When every other byte in the local window is the same non-zero value
                    # (e.g. $2C $9B $00 $9B $16 $9B …), the data is an interleaved
                    # lookup/timing table, not sprite graphics.  Showing pixel art for
                    # such bytes is misleading.  We check a 6-byte window (3 pairs)
                    # centred on the current byte.
                    def _in_alternating_run(rom_data, offset, data_s, data_e):
                        """Return True if this byte is part of an alternating-value run."""
                        # Strategy: look for an alternating-byte run of length >= 4
                        # starting at 'offset' itself (phase 0) and at 'offset-1' (phase 1).
                        # This handles cases where null bytes precede the alternating block
                        # and shift the window's even/odd alignment away from the pattern.
                        def _is_arithmetic_progression(seq, min_len=3):
                            """Return True if seq is a non-trivial arithmetic progression (step != 0)."""
                            if len(seq) < min_len:
                                return False
                            step = seq[1] - seq[0]
                            if step == 0:
                                return False  # constant sequence handled by constant check
                            return all(seq[i] - seq[i-1] == step for i in range(2, len(seq)))

                        def _has_alt_run_from(start, min_len=4):
                            """Check if there is an alternating run of >= min_len starting at start.
                            
                            Detects two kinds of interleaved table patterns:
                            1. Constant-interleaved: all even or all odd bytes are the same value
                            2. Progression-interleaved: even or odd bytes form an arithmetic progression
                            Both patterns indicate lookup/timing tables rather than sprite graphics.
                            """
                            end = min(data_e, start + 16)
                            seg = list(rom_data[start:end])
                            if len(seg) < min_len:
                                return False
                            evens = seg[0::2]
                            odds  = seg[1::2]
                            # Constant interleaved (original check)
                            if len(evens) >= 2 and len(set(evens)) == 1 and evens[0] != 0:
                                return True
                            if len(odds) >= 2 and len(set(odds)) == 1 and odds[0] != 0:
                                return True
                            # Arithmetic-progression interleaved: even or odd subsequence
                            # forms a non-trivial progression (e.g. river bank convergence
                            # tables where left bank increases +4 while right bank decreases -4).
                            if len(evens) >= 3 and _is_arithmetic_progression(evens):
                                return True
                            if len(odds) >= 3 and _is_arithmetic_progression(odds):
                                return True
                            return False

                        # Phase 0: run starts AT this offset
                        if _has_alt_run_from(offset):
                            return True
                        # Phase 1: run starts one byte BEFORE (offset is 2nd byte of pair)
                        if offset > data_s and _has_alt_run_from(offset - 1):
                            return True
                        # Fallback: broader window check (original logic, both phases)
                        for win_start_off in range(max(data_s, offset - 6), offset + 1):
                            win_end = min(data_e, win_start_off + 16)
                            window = list(rom_data[win_start_off:win_end])
                            if len(window) < 4:
                                continue
                            even_bytes = window[0::2]
                            odd_bytes  = window[1::2]
                            if len(set(even_bytes)) == 1 and even_bytes[0] != 0:
                                return True
                            if len(odd_bytes) >= 2 and len(set(odd_bytes)) == 1 and odd_bytes[0] != 0:
                                return True
                            # Arithmetic progression check in fallback window too
                            if len(even_bytes) >= 3 and _is_arithmetic_progression(even_bytes):
                                return True
                            if len(odd_bytes) >= 3 and _is_arithmetic_progression(odd_bytes):
                                return True
                        return False

                    suppress_visual = _in_alternating_run(rom, pc, data_start, data_end)
                    # Also suppress pixel art for the code-like prefix at the start
                    # of this data block (dead code / unreachable stub before real data).
                    if pc < data_code_prefix_end:
                        suppress_visual = True
                    visual = byte_to_ascii_art(byte_val, style='double') if not suppress_visual else ''
                    
                    # Build the line based on enabled flags
                    line_parts = []
                    if SHOW_ADDRESSES:
                        line_parts.append(f'${addr:04X}:')
                    line_parts.append(f'.byte ${byte_val:02X}')
                    
                    line = indent + ' '.join(line_parts)
                    
                    # Use centralized alignment calculation
                    align_column = calculate_alignment_column()
                    
                    # Combine visual with TIA comment if present
                    if tia_comment:
                        combined_comment = f'{visual} | {tia_comment}'
                    else:
                        combined_comment = visual
                    
                    # Add visual as comment
                    line = f'{line:<{align_column}} ; {combined_comment}'
                    out.write(line + '\n')
                else:
                    # Output data in rows of 16 bytes (original format)
                    if (pc - data_start) % 16 == 0:
                        if SHOW_ADDRESSES:
                            out.write(f'{indent}${addr:04X}: .byte ')
                        else:
                            out.write(f'{indent}.byte ')
                    
                    out.write(f'${rom[pc]:02X}')
                    
                    # Determine if the NEXT byte has a mid-block label (forces end of row)
                    next_pc = pc + 1
                    next_has_label = False
                    next_is_new_bank = False
                    if next_pc < rom_size:
                        next_bank_num, next_mem_addr_val = get_bank_info_for_offset(
                            next_pc, rom_size, bank_scheme,
                            output_bank_count, output_bank_size
                        )
                        if next_bank_num != bank_num:
                            next_is_new_bank = True
                        elif next_pc not in code_addresses and next_mem_addr_val in labels:
                            next_has_label = True
                    
                    # Check if we should add comma or newline
                    if (pc - data_start) % 16 == 15 or pc + 1 >= rom_size or (pc + 1) in code_addresses or next_has_label or next_is_new_bank:
                        # End of line - add TIA comment if present, then newline
                        if tia_comment and SHOW_COMMENTS:
                            # Get the current line content and pad it
                            align_column = calculate_alignment_column()
                            # Note: We don't have the full line here, so just add space and comment
                            out.write(f'  ; {tia_comment}')
                        out.write('\n')
                    else:
                        # More bytes on this line - add comma
                        out.write(',')
                
                # Clear visualization data at end of block
                if pc + 1 >= rom_size or (pc + 1) in code_addresses:
                    data_visualization = None
                    under_label = False  # Reset when leaving data block
                
                pc += 1
        
        # Add cross-reference summary at end of file if enabled
        if SHOW_XREFS and xref:
            out.write(f"\n; ============================================================================\n")
            out.write(f"; CROSS-REFERENCE SUMMARY\n")
            out.write(f"; ============================================================================\n")
            out.write(f";\n")
            out.write(f"; This section shows which subroutines call which other subroutines.\n")
            out.write(f";\n")
            
            # Get all subroutines (both callers and callees)
            all_subs = sorted(set(xref.calls.keys()) | set(xref.called_by.keys()))
            
            if all_subs:
                out.write(f"; Total subroutines: {len(all_subs)}\n")
                out.write(f"; Total calls: {sum(xref.call_counts.values())}\n")
                out.write(f";\n")
                
                # Output each subroutine and what it calls / what calls it
                for sub_addr in all_subs:
                    sub_name = labels.get(sub_addr, f"${sub_addr:04X}")
                    out.write(f"; {sub_name} (${sub_addr:04X}):\n")
                    
                    # What this subroutine calls
                    if sub_addr in xref.calls and xref.calls[sub_addr]:
                        out.write(f";   Calls:\n")
                        for called_addr in sorted(xref.calls[sub_addr]):
                            called_name = labels.get(called_addr, f"${called_addr:04X}")
                            out.write(f";     - {called_name} (${called_addr:04X})\n")
                    
                    # What calls this subroutine
                    if sub_addr in xref.called_by and xref.called_by[sub_addr]:
                        out.write(f";   Called by:\n")
                        for caller_addr in sorted(xref.called_by[sub_addr]):
                            caller_name = labels.get(caller_addr, f"${caller_addr:04X}")
                            out.write(f";     - {caller_name} (${caller_addr:04X})\n")
                    
                    # Dispatched via indirect JMP?
                    if sub_addr in xref.dispatch_targets and xref.dispatch_targets[sub_addr]:
                        out.write(f";   Dispatched from (JMP indirect):\n")
                        for site_addr in sorted(xref.dispatch_targets[sub_addr]):
                            site_name = labels.get(site_addr, f"${site_addr:04X}")
                            out.write(f";     - {site_name} (${site_addr:04X}) via JMP ($zp)\n")
                    
                    out.write(f";\n")
            else:
                out.write(f"; No subroutines found.\n")
                out.write(f";\n")
    
    print(f"Smart disassembly written to: {output_path}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Smart 6502 Disassembler with Code Flow Analysis',
        epilog='Example: python smart_disassembler.py rom.a26 --visualize-data'
    )
    parser.add_argument('rom', metavar='rom_file.ext', nargs='?', help='ROM file to disassemble (.a26, .bin, etc.)')
    parser.add_argument('--output', '-o', help='Output file (default: input filename with .asm extension)')
    parser.add_argument('--comments', '-c', action='store_true', help='Enable instruction comments')
    parser.add_argument('--addresses', action='store_true', help='Show memory addresses ($Fxxx) - breaks assembly!')
    parser.add_argument('--hex', action='store_true', help='Show hex byte values - breaks assembly!')
    parser.add_argument('--visualize-data', action='store_true', help='Show ASCII art visualization for graphics data')
    parser.add_argument('--disable-labels', action='store_true', help='Disable automatic label generation')
    parser.add_argument('--cycles', action='store_true', help='Show CPU cycle counts for each instruction')
    parser.add_argument('--xrefs', action='store_true', help='Show cross-references (which subroutines call which)')
    parser.add_argument('--show-flags', action='store_true', help='Show processor flags affected by each instruction (N V Z C etc.)')
    parser.add_argument('--show-operations', action='store_true', help='Show operation descriptions (A = A + M, etc.)')
    
    args = parser.parse_args()
    
    # Auto-generate output filename if not specified
    if args.output:
        output_path = args.output
    else:
        # Get the base filename without extension and add .asm
        base_name = os.path.splitext(args.rom)[0]
        output_path = base_name + '.asm'
    
    # Store options globally so they can be accessed by the disassembler
    global SHOW_COMMENTS, SHOW_ADDRESSES, SHOW_HEX, VISUALIZE_DATA, SHOW_LABELS, SHOW_CYCLES, SHOW_XREFS, SHOW_FLAGS, SHOW_OPERATIONS
    SHOW_COMMENTS = args.comments
    SHOW_ADDRESSES = args.addresses  # OFF by default (assembler-safe), use --addresses to enable
    SHOW_HEX = args.hex  # OFF by default (assembler-safe), use --hex to enable
    VISUALIZE_DATA = args.visualize_data
    SHOW_LABELS = not args.disable_labels  # Labels ON by default
    SHOW_CYCLES = args.cycles  # Cycle counting OFF by default, use --cycles to enable
    SHOW_XREFS = args.xrefs  # Cross-references OFF by default, use --xrefs to enable
    SHOW_FLAGS = args.show_flags  # Processor flags OFF by default, use --show-flags to enable
    SHOW_OPERATIONS = args.show_operations  # Operation descriptions OFF by default, use --show-operations to enable
    
    disassemble_smart(args.rom, output_path)
    print("Done!")
