"""
Symbols and Tracking Module - Consolidated symbol tables and code tracking

This module consolidates the following modules into a single file:
- atari2600_symbols.py: Atari 2600 hardware registers and memory map symbols
- code_comments.py: Intelligent comment generation for disassembly
- variable_tracker.py: Variable and zero-page usage tracking
- cross_referencer.py: Cross-reference tracking for jumps, branches, and calls

These modules work together to provide meaningful symbol names, track
variable usage, and generate cross-references for better code understanding.
"""

from typing import Dict, List, Set, Tuple, Optional
from typing import Dict, List, Tuple, Optional, Set
from typing import Optional
from typing import Optional, List, Tuple

# ============================================================================
# ATARI2600 SYMBOLS
# ============================================================================


from typing import Optional, List, Tuple

# Memory map constants
TIA_BASE = 0x00
TIA_SIZE = 0x80
RIOT_BASE = 0x0280
RIOT_END = 0x0297

# TIA (Television Interface Adapter) Write Registers
TIA_WRITE = {
    0x00: 'VSYNC',   # Vertical sync
    0x01: 'VBLANK',  # Vertical blank
    0x02: 'WSYNC',   # Wait for sync
    0x03: 'RSYNC',   # Reset sync
    0x04: 'NUSIZ0',  # Number-size player/missile 0
    0x05: 'NUSIZ1',  # Number-size player/missile 1
    0x06: 'COLUP0',  # Color-luminance player 0
    0x07: 'COLUP1',  # Color-luminance player 1
    0x08: 'COLUPF',  # Color-luminance playfield
    0x09: 'COLUBK',  # Color-luminance background
    0x0A: 'CTRLPF',  # Control playfield, ball, collisions
    0x0B: 'REFP0',   # Reflect player 0
    0x0C: 'REFP1',   # Reflect player 1
    0x0D: 'PF0',     # Playfield register byte 0
    0x0E: 'PF1',     # Playfield register byte 1
    0x0F: 'PF2',     # Playfield register byte 2
    0x10: 'RESP0',   # Reset player 0
    0x11: 'RESP1',   # Reset player 1
    0x12: 'RESM0',   # Reset missile 0
    0x13: 'RESM1',   # Reset missile 1
    0x14: 'RESBL',   # Reset ball
    0x15: 'AUDC0',   # Audio control 0
    0x16: 'AUDC1',   # Audio control 1
    0x17: 'AUDF0',   # Audio frequency 0
    0x18: 'AUDF1',   # Audio frequency 1
    0x19: 'AUDV0',   # Audio volume 0
    0x1A: 'AUDV1',   # Audio volume 1
    0x1B: 'GRP0',    # Graphics register player 0
    0x1C: 'GRP1',    # Graphics register player 1
    0x1D: 'ENAM0',   # Enable missile 0
    0x1E: 'ENAM1',   # Enable missile 1
    0x1F: 'ENABL',   # Enable ball
    0x20: 'HMP0',    # Horizontal motion player 0
    0x21: 'HMP1',    # Horizontal motion player 1
    0x22: 'HMM0',    # Horizontal motion missile 0
    0x23: 'HMM1',    # Horizontal motion missile 1
    0x24: 'HMBL',    # Horizontal motion ball
    0x25: 'VDELP0',  # Vertical delay player 0
    0x26: 'VDELP1',  # Vertical delay player 1
    0x27: 'VDELBL',  # Vertical delay ball
    0x28: 'RESMP0',  # Reset missile 0 to player 0
    0x29: 'RESMP1',  # Reset missile 1 to player 1
    0x2A: 'HMOVE',   # Apply horizontal motion
    0x2B: 'HMCLR',   # Clear horizontal motion registers
    0x2C: 'CXCLR',   # Clear collision latches
}

# TIA Read Registers (Collision Detection)
TIA_READ = {
    0x00: 'CXM0P',   # Collision M0-P1, M0-P0
    0x01: 'CXM1P',   # Collision M1-P0, M1-P1
    0x02: 'CXP0FB',  # Collision P0-PF, P0-BL
    0x03: 'CXP1FB',  # Collision P1-PF, P1-BL
    0x04: 'CXM0FB',  # Collision M0-PF, M0-BL
    0x05: 'CXM1FB',  # Collision M1-PF, M1-BL
    0x06: 'CXBLPF',  # Collision BL-PF
    0x07: 'CXPPMM',  # Collision P0-P1, M0-M1
    0x08: 'INPT0',   # Input port 0
    0x09: 'INPT1',   # Input port 1
    0x0A: 'INPT2',   # Input port 2
    0x0B: 'INPT3',   # Input port 3
    0x0C: 'INPT4',   # Input port 4 (fire button)
    0x0D: 'INPT5',   # Input port 5 (fire button)
}

# RIOT (RAM-I/O-Timer) Registers
RIOT = {
    0x0280: 'SWCHA',  # Port A data register (joystick inputs)
    0x0281: 'SWACNT', # Port A DDR
    0x0282: 'SWCHB',  # Port B data register (console switches)
    0x0283: 'SWBCNT', # Port B DDR
    0x0284: 'INTIM',  # Timer output
    0x0285: 'TIMINT', # Timer interrupt
    0x0294: 'TIM1T',  # Set 1 clock interval
    0x0295: 'TIM8T',  # Set 8 clock interval
    0x0296: 'TIM64T', # Set 64 clock interval
    0x0297: 'T1024T', # Set 1024 clock interval
}

def get_symbol_name(address: int) -> Optional[str]:
    """
    Get the symbolic name for a hardware register address.
    
    Args:
        address: Memory address to look up (0x00-0x7F for TIA, 0x0280-0x0297 for RIOT)
        
    Returns:
        Symbolic name string if address is a known hardware register, None otherwise
        
    Examples:
        >>> get_symbol_name(0x00)
        'VSYNC'
        >>> get_symbol_name(0x0284)
        'INTIM'
        >>> get_symbol_name(0x80)
        None
    """
    if address < TIA_SIZE:
        # TIA registers (0x00-0x7F)
        if address in TIA_WRITE:
            return TIA_WRITE[address]
        elif address in TIA_READ:
            return TIA_READ[address]
    elif RIOT_BASE <= address <= RIOT_END:
        # RIOT registers (0x0280-0x0297)
        if address in RIOT:
            return RIOT[address]
    return None

# Symbol descriptions for comments
SYMBOL_DESCRIPTIONS = {
    'CXM0P': 'Read collision M0-P1, M0-P0',
    'CXM1P': 'Read collision M1-P0, M1-P1',
    'CXP0FB': 'Read collision P0-PF, P0-BL',
    'CXP1FB': 'Read collision P1-PF, P1-BL',
    'CXM0FB': 'Read collision M0-PF, M0-BL',
    'CXM1FB': 'Read collision M1-PF, M1-BL',
    'CXBLPF': 'Read collision BL-PF',
    'CXPPMM': 'Read collision P0-P1, M0-M1',
    'INPT0': 'Read input port 0',
    'INPT1': 'Read input port 1',
    'INPT2': 'Read input port 2',
    'INPT3': 'Read input port 3',
    'INPT4': 'Read input port 4 (fire button)',
    'INPT5': 'Read input port 5 (fire button)',
    'VSYNC': 'Vertical sync set-clear',
    'VBLANK': 'Vertical blank set-clear',
    'WSYNC': 'Wait for horizontal blank',
    'RSYNC': 'Reset horizontal sync counter',
    'NUSIZ0': 'Number-size player/missile 0',
    'NUSIZ1': 'Number-size player/missile 1',
    'COLUP0': 'Color-luminance player 0',
    'COLUP1': 'Color-luminance player 1',
    'COLUPF': 'Color-luminance playfield',
    'COLUBK': 'Color-luminance background',
    'CTRLPF': 'Control playfield, ball, collisions',
    'REFP0': 'Reflection player 0',
    'REFP1': 'Reflection player 1',
    'PF0': 'Playfield register byte 0',
    'PF1': 'Playfield register byte 1',
    'PF2': 'Playfield register byte 2',
    'RESP0': 'Reset player 0',
    'RESP1': 'Reset player 1',
    'RESM0': 'Reset missile 0',
    'RESM1': 'Reset missile 1',
    'RESBL': 'Reset ball',
    'AUDC0': 'Audio control 0',
    'AUDC1': 'Audio control 1',
    'AUDF0': 'Audio frequency 0',
    'AUDF1': 'Audio frequency 1',
    'AUDV0': 'Audio volume 0',
    'AUDV1': 'Audio volume 1',
    'GRP0': 'Graphics register player 0',
    'GRP1': 'Graphics register player 1',
    'ENAM0': 'Graphics enable missile 0',
    'ENAM1': 'Graphics enable missile 1',
    'ENABL': 'Graphics enable ball',
    'HMP0': 'Horizontal motion player 0',
    'HMP1': 'Horizontal motion player 1',
    'HMM0': 'Horizontal motion missile 0',
    'HMM1': 'Horizontal motion missile 1',
    'HMBL': 'Horizontal motion ball',
    'VDELP0': 'Vertical delay player 0',
    'VDELP1': 'Vertical delay player 1',
    'VDELBL': 'Vertical delay ball',
    'RESMP0': 'Reset missile 0 to player 0',
    'RESMP1': 'Reset missile 1 to player 1',
    'HMOVE': 'Apply horizontal motion',
    'HMCLR': 'Clear horizontal motion registers',
    'CXCLR': 'Clear collision latches',
    'SWCHA': 'Port A; input or output (read or write)',
    'SWACNT': 'Port A DDR, 0=input, 1=output',
    'SWCHB': 'Port B; console switches (read only)',
    'SWBCNT': 'Port B DDR (hardwired as input)',
    'INTIM': 'Timer output (read only)',
    'TIMINT': 'Timer interrupt (read only)',
    'TIM1T': 'Set 1 clock interval (838 nsec/interval)',
    'TIM8T': 'Set 8 clock interval (6.7 usec/interval)',
    'TIM64T': 'Set 64 clock interval (53.6 usec/interval)',
    'T1024T': 'Set 1024 clock interval (858.2 usec/interval)',
}

def get_all_symbols() -> List[Tuple[str, int, str, str]]:
    """
    Get all symbol definitions for output, organized by category.
    
    Returns:
        List of (name, address, description, category) tuples for all hardware registers.
        Categories: 'COLLISION', 'INPUT', 'SYNC', 'GRAPHICS', 'COLOR', 'AUDIO', 'MOTION', 'RIOT'
        
    Example:
        >>> symbols = get_all_symbols()
        >>> symbols[0]
        ('CXM0P', 0, 'Read collision M0-P1, M0-P0', 'COLLISION')
    """
    symbols = []
    
    # Collision Detection (Read-only)
    collision_regs = ['CXM0P', 'CXM1P', 'CXP0FB', 'CXP1FB', 'CXM0FB', 'CXM1FB', 'CXBLPF', 'CXPPMM', 'CXCLR']
    for addr, name in sorted(TIA_READ.items()):
        if name in collision_regs:
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'COLLISION'))
    # Add CXCLR from write registers
    for addr, name in sorted(TIA_WRITE.items()):
        if name == 'CXCLR':
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'COLLISION'))
    
    # Input Ports (Read-only)
    for addr, name in sorted(TIA_READ.items()):
        if name.startswith('INPT'):
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'INPUT'))
    
    # Sync and Timing
    sync_regs = ['VSYNC', 'VBLANK', 'WSYNC', 'RSYNC']
    for addr, name in sorted(TIA_WRITE.items()):
        if name in sync_regs:
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'SYNC'))
    
    # Graphics (Players, Missiles, Ball, Playfield)
    graphics_regs = ['NUSIZ0', 'NUSIZ1', 'GRP0', 'GRP1', 'ENAM0', 'ENAM1', 'ENABL',
                     'REFP0', 'REFP1', 'PF0', 'PF1', 'PF2', 'CTRLPF',
                     'RESP0', 'RESP1', 'RESM0', 'RESM1', 'RESBL',
                     'VDELP0', 'VDELP1', 'VDELBL', 'RESMP0', 'RESMP1']
    for addr, name in sorted(TIA_WRITE.items()):
        if name in graphics_regs:
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'GRAPHICS'))
    
    # Color
    color_regs = ['COLUP0', 'COLUP1', 'COLUPF', 'COLUBK']
    for addr, name in sorted(TIA_WRITE.items()):
        if name in color_regs:
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'COLOR'))
    
    # Audio
    audio_regs = ['AUDC0', 'AUDC1', 'AUDF0', 'AUDF1', 'AUDV0', 'AUDV1']
    for addr, name in sorted(TIA_WRITE.items()):
        if name in audio_regs:
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'AUDIO'))
    
    # Horizontal Motion
    motion_regs = ['HMP0', 'HMP1', 'HMM0', 'HMM1', 'HMBL', 'HMOVE', 'HMCLR']
    for addr, name in sorted(TIA_WRITE.items()):
        if name in motion_regs:
            desc = SYMBOL_DESCRIPTIONS.get(name, '')
            symbols.append((name, addr, desc, 'MOTION'))
    
    # RIOT (I/O and Timer)
    for addr, name in sorted(RIOT.items()):
        desc = SYMBOL_DESCRIPTIONS.get(name, '')
        symbols.append((name, addr, desc, 'RIOT'))
    
    return symbols


# ============================================================================
# CODE COMMENTS
# ============================================================================


from typing import Optional

def decode_nusiz(value: int, player_num: str) -> str:
    """Decode NUSIZ register value to human-readable format."""
    missile_size = (value >> 4) & 0x03
    player_missile_config = value & 0x07
    
    missile_widths = {0: "1 clock", 1: "2 clocks", 2: "4 clocks", 3: "8 clocks"}
    
    configs = {
        0: "1 copy, normal size",
        1: "2 copies close (8 clocks), normal size",
        2: "2 copies medium (24 clocks), normal size",
        3: "3 copies close (8 clocks), normal size",
        4: "2 copies wide (56 clocks), normal size",
        5: "1 copy, double width",
        6: "3 copies medium (24 clocks), normal size",
        7: "1 copy, quad width"
    }
    
    return f"P{player_num}/M{player_num}: {configs.get(player_missile_config, 'unknown')}, missile {missile_widths.get(missile_size, 'unknown')}"

def decode_ctrlpf(value: int) -> str:
    """Decode CTRLPF register value to human-readable format."""
    parts = []
    
    if value & 0x01:
        parts.append("playfield reflected")
    else:
        parts.append("playfield normal")
    
    if value & 0x02:
        parts.append("score mode")
    
    if value & 0x04:
        parts.append("PF priority over players")
    
    ball_size = (value >> 4) & 0x03
    ball_widths = {0: "1 clock", 1: "2 clocks", 2: "4 clocks", 3: "8 clocks"}
    parts.append(f"ball {ball_widths.get(ball_size, 'unknown')}")
    
    return ", ".join(parts)

def decode_audc(value: int) -> str:
    """Decode AUDC register value to sound type."""
    sound_types = {
        0x00: "set to 1 (silence)",
        0x01: "4-bit poly (buzzy)",
        0x02: "div 15 → 4-bit poly",
        0x03: "5-bit poly → 4-bit poly",
        0x04: "pure tone (div 2)",
        0x05: "pure tone (div 2)",
        0x06: "pure tone (div 31)",
        0x07: "5-bit poly → div 2",
        0x08: "9-bit poly (white noise)",
        0x09: "5-bit poly",
        0x0A: "pure tone (div 31)",
        0x0B: "set last 4 bits to 1",
        0x0C: "pure tone (div 6)",
        0x0D: "pure tone (div 6)",
        0x0E: "pure tone (div 93)",
        0x0F: "5-bit poly div 6"
    }
    return sound_types.get(value & 0x0F, "unknown sound type")

def decode_audf(value: int) -> str:
    """Decode AUDF register value to frequency info."""
    divisor = (value & 0x1F) + 1  # 0-31 becomes 1-32
    base_freq = 31400  # ~31.4 KHz base frequency
    freq = base_freq / divisor
    
    if freq > 1000:
        return f"÷{divisor} (~{freq/1000:.1f} KHz)"
    else:
        return f"÷{divisor} (~{freq:.0f} Hz)"

def get_instruction_comment(mnemonic: str, operand_str: str, addr: int) -> str:
    """
    Generate an intelligent comment for an instruction.
    
    Args:
        mnemonic: Instruction mnemonic (e.g., 'LDA', 'STA', 'JMP')
        operand_str: Operand string (e.g., 'GRP0', '#$00', '$F000')
        addr: Address of the instruction
        
    Returns:
        Comment string explaining what the instruction does, or empty string
    """
    
    # Strip addressing mode prefixes to get the actual symbol name
    clean_operand = operand_str.lstrip('<>#$')
    
    # Graphics-related comments (enhanced with Stella documentation)
    if clean_operand in ['GRP0', 'GRP1']:
        return f"Update player {clean_operand[-1]} graphics (8-bit sprite data, D7=left)"
    elif clean_operand == 'ENABL':
        return "Enable/disable ball sprite (D1: 1=enable, 0=disable)"
    elif clean_operand in ['ENAM0', 'ENAM1']:
        return f"Enable/disable missile {clean_operand[-1]} (D1: 1=enable, 0=disable)"
    elif clean_operand in ['PF0', 'PF1', 'PF2']:
        pf_bits = {'PF0': '4 bits (D7-D4)', 'PF1': '8 bits', 'PF2': '8 bits'}
        return f"Set playfield register {clean_operand[-1]} ({pf_bits[clean_operand]})"
    elif clean_operand == 'COLUPF':
        return "Set playfield/ball color (D7-D4: color, D3-D1: luminosity)"
    elif clean_operand == 'COLUBK':
        return "Set background color (D7-D4: color, D3-D1: luminosity)"
    elif clean_operand in ['COLUP0', 'COLUP1']:
        return f"Set player/missile {clean_operand[-1]} color (D7-D4: color, D3-D1: lum)"
    elif clean_operand == 'CTRLPF':
        return "Control playfield (D0: reflect, D1: score, D2: priority, D5-D4: ball size)"
    elif clean_operand in ['REFP0', 'REFP1']:
        return f"Reflect player {clean_operand[-1]} (D3: 1=reflect, 0=normal)"
    elif clean_operand in ['VDELP0', 'VDELP1']:
        return f"Vertical delay player {clean_operand[-1]} (D0: 1=delay 1 line, 0=no delay)"
    elif clean_operand == 'VDELBL':
        return "Vertical delay ball (D0: 1=delay 1 line, 0=no delay)"
    
    # Position/motion comments (enhanced with Stella documentation)
    elif clean_operand in ['RESP0', 'RESP1']:
        return f"Reset player {clean_operand[-1]} horizontal position (strobe)"
    elif clean_operand in ['RESM0', 'RESM1']:
        return f"Reset missile {clean_operand[-1]} horizontal position (strobe)"
    elif clean_operand == 'RESBL':
        return "Reset ball horizontal position (strobe)"
    elif clean_operand in ['RESMP0', 'RESMP1']:
        num = clean_operand[-1]
        return f"Reset missile {num} to player {num} center (D1: 1=lock, 0=unlock)"
    elif clean_operand in ['HMP0', 'HMP1']:
        return f"Horizontal motion player {clean_operand[-1]} (D7-D4: -8 to +7)"
    elif clean_operand in ['HMM0', 'HMM1']:
        return f"Horizontal motion missile {clean_operand[-1]} (D7-D4: -8 to +7)"
    elif clean_operand == 'HMBL':
        return "Horizontal motion ball (D7-D4: -8 to +7)"
    elif clean_operand == 'HMOVE':
        return "Apply horizontal motion (MUST follow WSYNC!)"
    elif clean_operand == 'HMCLR':
        return "Clear all horizontal motion registers to zero"
    
    # Sync/timing comments (enhanced with Stella documentation)
    elif clean_operand == 'WSYNC':
        return "Wait for horizontal blank (halts CPU until HBlank, 68 clocks)"
    elif clean_operand == 'VSYNC':
        return "Vertical sync signal (D1: 1=start VSYNC, 0=stop, need 3 scanlines)"
    elif clean_operand == 'VBLANK':
        return "Vertical blank (D1: blank on/off, D6: latch I4/I5, D7: dump I0-I3)"
    elif clean_operand == 'RSYNC':
        return "Reset horizontal sync counter (testing only)"
    
    # Audio comments (enhanced with Stella documentation)
    elif clean_operand in ['AUDC0', 'AUDC1']:
        return f"Audio control channel {clean_operand[-1]} (D3-D0: sound type)"
    elif clean_operand in ['AUDF0', 'AUDF1']:
        return f"Audio frequency channel {clean_operand[-1]} (D4-D0: divide 30KHz by 1-32)"
    elif clean_operand in ['AUDV0', 'AUDV1']:
        return f"Audio volume channel {clean_operand[-1]} (D3-D0: 0=off, 15=max)"
    
    # Input/collision comments
    elif clean_operand == 'SWCHA':
        return "Read joystick inputs"
    elif clean_operand == 'SWCHB':
        return "Read console switches (RESET/SELECT)"
    elif clean_operand == 'CXCLR':
        return "Clear collision detection latches"
    elif clean_operand.startswith('CX'):
        return "Collision detection"
    
    # Timer comments
    elif clean_operand == 'INTIM':
        return "Read timer value"
    elif clean_operand == 'TIM64T':
        return "Set timer (64 clock interval)"
    elif clean_operand in ['TIM1T', 'TIM8T', 'T1024T']:
        return f"Set timer ({clean_operand[3:-1]} clock interval)"
    
    # Size/number comments
    elif clean_operand in ['NUSIZ0', 'NUSIZ1']:
        return f"Number/size of player/missile {clean_operand[-1]}"
    
    # Control flow comments
    elif mnemonic == 'JSR':
        return "Call subroutine"
    elif mnemonic == 'RTS':
        return "Return from subroutine"
    elif mnemonic == 'JMP':
        return "Jump"
    elif mnemonic in ['BEQ', 'BNE', 'BPL', 'BMI', 'BCC', 'BCS', 'BVC', 'BVS']:
        branch_names = {
            'BEQ': 'Branch if equal (zero)',
            'BNE': 'Branch if not equal (not zero)',
            'BPL': 'Branch if positive',
            'BMI': 'Branch if negative',
            'BCC': 'Branch if carry clear',
            'BCS': 'Branch if carry set',
            'BVC': 'Branch if overflow clear',
            'BVS': 'Branch if overflow set'
        }
        return f"{branch_names.get(mnemonic, 'Branch')}"
    
    # Stack operations
    elif mnemonic in ['PHA', 'PHP']:
        return "Push to stack"
    elif mnemonic in ['PLA', 'PLP']:
        return "Pull from stack"
    
    # Common patterns
    elif mnemonic == 'LDA' and operand_str.startswith('#$00'):
        return "Clear accumulator"
    elif mnemonic == 'LDX' and operand_str.startswith('#$00'):
        return "Clear X register"
    elif mnemonic == 'LDY' and operand_str.startswith('#$00'):
        return "Clear Y register"
    elif mnemonic == 'CLC':
        return "Clear carry flag"
    elif mnemonic == 'SEC':
        return "Set carry flag"
    elif mnemonic == 'CLD':
        return "Clear decimal mode"
    elif mnemonic == 'SED':
        return "Set decimal mode"
    elif mnemonic == 'SEI':
        return "Disable interrupts"
    elif mnemonic == 'CLI':
        return "Enable interrupts"
    elif mnemonic == 'DEX':
        return "Decrement X"
    elif mnemonic == 'DEY':
        return "Decrement Y"
    elif mnemonic == 'INX':
        return "Increment X"
    elif mnemonic == 'INY':
        return "Increment Y"
    elif mnemonic == 'TAX':
        return "Transfer A to X"
    elif mnemonic == 'TAY':
        return "Transfer A to Y"
    elif mnemonic == 'TXA':
        return "Transfer X to A"
    elif mnemonic == 'TYA':
        return "Transfer Y to A"
    elif mnemonic == 'TSX':
        return "Transfer stack pointer to X"
    elif mnemonic == 'TXS':
        return "Transfer X to stack pointer"
    
    # Basic load/store operations
    elif mnemonic == 'LDA':
        return "Load accumulator"
    elif mnemonic == 'LDX':
        return "Load X register"
    elif mnemonic == 'LDY':
        return "Load Y register"
    elif mnemonic == 'STA':
        return "Store accumulator"
    elif mnemonic == 'STX':
        return "Store X register"
    elif mnemonic == 'STY':
        return "Store Y register"
    
    # Arithmetic operations
    elif mnemonic == 'ADC':
        return "Add with carry"
    elif mnemonic == 'SBC':
        return "Subtract with carry"
    elif mnemonic == 'INC':
        return "Increment memory"
    elif mnemonic == 'DEC':
        return "Decrement memory"
    
    # Logical operations
    elif mnemonic == 'AND':
        return "Logical AND"
    elif mnemonic == 'ORA':
        return "Logical OR"
    elif mnemonic == 'EOR':
        return "Exclusive OR"
    elif mnemonic == 'BIT':
        return "Bit test"
    
    # Shift/rotate operations
    elif mnemonic == 'ASL':
        return "Arithmetic shift left"
    elif mnemonic == 'LSR':
        return "Logical shift right"
    elif mnemonic == 'ROL':
        return "Rotate left"
    elif mnemonic == 'ROR':
        return "Rotate right"
    
    # Compare operations
    elif mnemonic == 'CMP':
        return "Compare accumulator"
    elif mnemonic == 'CPX':
        return "Compare X register"
    elif mnemonic == 'CPY':
        return "Compare Y register"
    
    # Special operations
    elif mnemonic == 'NOP':
        return "No operation"
    elif mnemonic == 'BRK':
        return "Break (software interrupt)"
    elif mnemonic == 'RTI':
        return "Return from interrupt"
    
    return ""  # No comment for this instruction

def get_section_comment(addr: int, prev_addr: Optional[int] = None) -> str:
    """
    Generate section headers for major code regions.
    
    Args:
        addr: Current address
        prev_addr: Previous address (optional)
        
    Returns:
        Section header comment or empty string
    """
    
    # Known important addresses in Frogs and Flies
    if addr == 0xF000:
        return "\n; ============================================================================\n; Display Kernel - Main scanline rendering loop\n; ============================================================================\n"
    elif addr == 0xF178:
        return "\n; ============================================================================\n; GAME START / RESET\n; Main entry point - initializes the system\n; ============================================================================\n"
    elif addr == 0xF194:
        return "\n; ============================================================================\n; MAIN GAME LOOP\n; Runs continuously - handles timing, input, game logic, and display\n; ============================================================================\n"
    
    return ""


# ============================================================================
# VARIABLE TRACKER
# ============================================================================


from typing import Dict, List, Tuple, Optional, Set
from core_opcodes import OPCODES

class VariableTracker:
    """
    Tracks and analyzes zero page variable usage in Atari 2600 ROMs.
    
    Generates meaningful variable names based on:
    - TIA register usage patterns (graphics, color, audio, etc.)
    - 16-bit pointer pair detection
    - Read/write patterns (constants, temps, flags)
    - Indexed access patterns (arrays)
    """
    
    def __init__(self) -> None:
        """Initialize the variable tracker with empty state."""
        self.variables: Dict[int, Dict] = {}  # addr -> {'name': str, 'reads': int, 'writes': int, 'type': str}
        self.pairs: List[Tuple[int, int]] = []  # List of (low_addr, high_addr) for 16-bit pointers
        
    def analyze_code(self, rom: bytearray, code_addresses: Set[int], base_addr: int) -> None:
        """
        Analyze code to find zero page variable usage patterns.
        
        Args:
            rom: ROM data as bytearray
            code_addresses: Set of addresses identified as code
            base_addr: Base address where ROM is loaded in memory
            
        Note:
            This method populates self.variables and self.pairs based on analysis.
        """
        rom_size = len(rom)
        
        # Track all zero page accesses
        zp_usage = {}  # addr -> {'reads': [], 'writes': [], 'indexed_x': bool, 'indexed_y': bool, 'tia_usage': {}}
        
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
            
            # Check for zero page operations
            if size >= 2 and mode in ['zeropage', 'zeropage_x', 'zeropage_y']:
                zp_addr = rom[pc + 1]
                
                # Only track RAM area ($80-$FF)
                if 0x80 <= zp_addr <= 0xFF:
                    if zp_addr not in zp_usage:
                        zp_usage[zp_addr] = {
                            'reads': [],
                            'writes': [],
                            'indexed_x': False,
                            'indexed_y': False,
                            'tia_usage': {}  # Track which TIA registers this var is used with
                        }
                    
                    # Determine if it's a read or write
                    is_write = mnemonic in ['STA', 'STX', 'STY', 'SAX', 'AHX', 'SHY', 'SHX', 'TAS']
                    is_read = mnemonic in ['LDA', 'LDX', 'LDY', 'LAX', 'CMP', 'CPX', 'CPY', 
                                          'BIT', 'AND', 'ORA', 'EOR', 'ADC', 'SBC',
                                          'INC', 'DEC', 'ASL', 'LSR', 'ROL', 'ROR',
                                          'DCP', 'ISC', 'SLO', 'RLA', 'SRE', 'RRA']
                    
                    if is_write:
                        zp_usage[zp_addr]['writes'].append((pc, mnemonic))
                    if is_read:
                        zp_usage[zp_addr]['reads'].append((pc, mnemonic))
                    
                    # Track indexing
                    if mode == 'zeropage_x':
                        zp_usage[zp_addr]['indexed_x'] = True
                    elif mode == 'zeropage_y':
                        zp_usage[zp_addr]['indexed_y'] = True
            
            pc += size
        
        # Analyze TIA register usage patterns
        self._analyze_tia_patterns(rom, code_addresses, zp_usage)
        
        # Detect 16-bit pointer pairs (consecutive addresses used together)
        self._detect_pointer_pairs(zp_usage)
        
        # Generate variable names based on usage patterns
        self._generate_variable_names(zp_usage)
        
    def _analyze_tia_patterns(self, rom: bytearray, code_addresses: Set[int], zp_usage: Dict) -> None:
        """
        Analyze how variables are used with TIA registers to infer their purpose.
        
        Args:
            rom: ROM data as bytearray
            code_addresses: Set of addresses identified as code
            zp_usage: Dictionary tracking zero page usage patterns
            
        Note:
            Looks for LDA zp_var / STA TIA_register patterns to determine variable purpose.
        """
        rom_size = len(rom)
        
        # TIA register categories
        TIA_GRAPHICS = {0x1B: 'GRP0', 0x1C: 'GRP1', 0x0D: 'PF0', 0x0E: 'PF1', 0x0F: 'PF2'}
        TIA_COLOR = {0x06: 'COLUP0', 0x07: 'COLUP1', 0x08: 'COLUPF', 0x09: 'COLUBK'}
        TIA_POSITION = {0x10: 'RESP0', 0x11: 'RESP1', 0x12: 'RESM0', 0x13: 'RESM1', 0x14: 'RESBL'}
        TIA_MOTION = {0x20: 'HMP0', 0x21: 'HMP1', 0x22: 'HMM0', 0x23: 'HMM1', 0x24: 'HMBL'}
        TIA_AUDIO = {0x15: 'AUDC0', 0x16: 'AUDC1', 0x17: 'AUDF0', 0x18: 'AUDF1', 0x19: 'AUDV0', 0x1A: 'AUDV1'}
        
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
            
            # Look for pattern: LDA zp_var followed by STA TIA_register
            if mnemonic == 'LDA' and mode in ['zeropage', 'zeropage_x', 'zeropage_y'] and size >= 2:
                zp_addr = rom[pc + 1]
                if 0x80 <= zp_addr <= 0xFF:
                    # Look ahead for STA to TIA register
                    next_pc = pc + size
                    if next_pc < rom_size and next_pc in code_addresses:
                        next_opcode = rom[next_pc]
                        if next_opcode in OPCODES:
                            next_mnem, next_size, next_mode = OPCODES[next_opcode]
                            if next_mnem == 'STA' and next_mode == 'zeropage' and next_size >= 2:
                                tia_addr = rom[next_pc + 1]
                                
                                # Track which TIA register this variable feeds
                                if zp_addr in zp_usage:
                                    if tia_addr in TIA_GRAPHICS:
                                        zp_usage[zp_addr]['tia_usage'][TIA_GRAPHICS[tia_addr]] = zp_usage[zp_addr]['tia_usage'].get(TIA_GRAPHICS[tia_addr], 0) + 1
                                    elif tia_addr in TIA_COLOR:
                                        zp_usage[zp_addr]['tia_usage'][TIA_COLOR[tia_addr]] = zp_usage[zp_addr]['tia_usage'].get(TIA_COLOR[tia_addr], 0) + 1
                                    elif tia_addr in TIA_POSITION:
                                        zp_usage[zp_addr]['tia_usage'][TIA_POSITION[tia_addr]] = zp_usage[zp_addr]['tia_usage'].get(TIA_POSITION[tia_addr], 0) + 1
                                    elif tia_addr in TIA_MOTION:
                                        zp_usage[zp_addr]['tia_usage'][TIA_MOTION[tia_addr]] = zp_usage[zp_addr]['tia_usage'].get(TIA_MOTION[tia_addr], 0) + 1
                                    elif tia_addr in TIA_AUDIO:
                                        zp_usage[zp_addr]['tia_usage'][TIA_AUDIO[tia_addr]] = zp_usage[zp_addr]['tia_usage'].get(TIA_AUDIO[tia_addr], 0) + 1
            
            pc += size
    
    def _detect_pointer_pairs(self, zp_usage: Dict) -> None:
        """
        Detect 16-bit pointer pairs (consecutive low/high byte pairs).
        
        Args:
            zp_usage: Dictionary tracking zero page usage patterns
            
        Note:
            Pairs are detected when consecutive addresses are written within 10 bytes of each other.
        """
        addresses = sorted(zp_usage.keys())
        
        for i in range(len(addresses) - 1):
            low_addr = addresses[i]
            high_addr = addresses[i + 1]
            
            # Check if they're consecutive
            if high_addr == low_addr + 1:
                # Check if they're used close together in code
                low_writes = set(pc for pc, _ in zp_usage[low_addr]['writes'])
                high_writes = set(pc for pc, _ in zp_usage[high_addr]['writes'])
                
                # If writes are within 10 bytes of each other, likely a pointer pair
                for low_pc in low_writes:
                    for high_pc in high_writes:
                        if abs(high_pc - low_pc) <= 10:
                            self.pairs.append((low_addr, high_addr))
                            break
    
    def _generate_variable_names(self, zp_usage: Dict) -> None:
        """
        Generate meaningful variable names based on usage patterns.
        
        Args:
            zp_usage: Dictionary tracking zero page usage patterns
            
        Priority order for naming:
        1. TIA register usage (most specific: Sprite0Data, Player0Color, etc.)
        2. Pointer pairs (Pointer80, Pointer80Hi)
        3. Usage patterns (Array, Const, Temp, Flag, Var)
        """
        
        # Track which addresses are part of pointer pairs
        paired_addrs = set()
        for low, high in self.pairs:
            paired_addrs.add(low)
            paired_addrs.add(high)
        
        for addr, usage in zp_usage.items():
            read_count = len(usage['reads'])
            write_count = len(usage['writes'])
            tia_usage = usage.get('tia_usage', {})
            
            # Determine variable type and generate name
            var_type = 'byte'
            var_name = None
            
            # Check if it's part of a pointer pair
            is_pointer_low = any(addr == low for low, high in self.pairs)
            is_pointer_high = any(addr == high for low, high in self.pairs)
            
            # First priority: TIA register usage patterns (most specific)
            if tia_usage and not is_pointer_low and not is_pointer_high:
                # Find most common TIA register this var is used with
                most_common_tia = max(tia_usage.items(), key=lambda x: x[1])[0] if tia_usage else None
                
                if most_common_tia:
                    if most_common_tia == 'GRP0':
                        var_type = 'sprite'
                        var_name = f'Sprite0Data{addr:02X}'
                    elif most_common_tia == 'GRP1':
                        var_type = 'sprite'
                        var_name = f'Sprite1Data{addr:02X}'
                    elif most_common_tia in ['PF0', 'PF1', 'PF2']:
                        var_type = 'playfield'
                        var_name = f'PlayfieldData{addr:02X}'
                    elif most_common_tia == 'COLUP0':
                        var_type = 'color'
                        var_name = f'Player0Color{addr:02X}'
                    elif most_common_tia == 'COLUP1':
                        var_type = 'color'
                        var_name = f'Player1Color{addr:02X}'
                    elif most_common_tia == 'COLUPF':
                        var_type = 'color'
                        var_name = f'PlayfieldColor{addr:02X}'
                    elif most_common_tia == 'COLUBK':
                        var_type = 'color'
                        var_name = f'BackgroundColor{addr:02X}'
                    elif most_common_tia in ['AUDC0', 'AUDF0', 'AUDV0']:
                        var_type = 'audio'
                        var_name = f'Sound0Data{addr:02X}'
                    elif most_common_tia in ['AUDC1', 'AUDF1', 'AUDV1']:
                        var_type = 'audio'
                        var_name = f'Sound1Data{addr:02X}'
                    elif most_common_tia in ['HMP0', 'HMP1', 'HMM0', 'HMM1', 'HMBL']:
                        var_type = 'motion'
                        var_name = f'MotionData{addr:02X}'
            
            # Second priority: Pointer pairs
            if not var_name:
                if is_pointer_low:
                    var_type = 'pointer'
                    var_name = f'Pointer{addr:02X}'
                elif is_pointer_high:
                    var_type = 'pointer_high'
                    var_name = f'Pointer{addr-1:02X}Hi'
            
            # Third priority: Usage patterns
            if not var_name:
                if usage['indexed_x'] or usage['indexed_y']:
                    var_type = 'array'
                    var_name = f'Array{addr:02X}'
                elif write_count == 0 and read_count > 0:
                    var_type = 'constant'
                    var_name = f'Const{addr:02X}'
                elif write_count > read_count * 3:
                    var_type = 'temp'
                    var_name = f'Temp{addr:02X}'
                elif read_count > write_count * 3:
                    var_type = 'flag'
                    var_name = f'Flag{addr:02X}'
                else:
                    var_type = 'var'
                    var_name = f'Var{addr:02X}'
            
            self.variables[addr] = {
                'name': var_name,
                'reads': read_count,
                'writes': write_count,
                'type': var_type
            }
    
    def get_variable_name(self, addr: int) -> Optional[str]:
        """
        Get the variable name for a zero page address.
        
        Args:
            addr: Zero page address (0x80-0xFF)
            
        Returns:
            Variable name string or None if address not tracked
        """
        if addr in self.variables:
            return self.variables[addr]['name']
        return None
    
    def get_all_variables(self) -> List[Tuple[int, Dict]]:
        """
        Get all tracked variables sorted by address.
        
        Returns:
            List of (address, variable_info) tuples sorted by address
        """
        return sorted(self.variables.items())
    
    def get_pointer_pairs(self) -> List[Tuple[int, int]]:
        """
        Get all detected 16-bit pointer pairs.
        
        Returns:
            List of (low_address, high_address) tuples
        """
        return self.pairs


# ============================================================================
# CROSS REFERENCER
# ============================================================================


from typing import Dict, List, Set, Tuple, Optional
from core_opcodes import OPCODES

class CrossReferencer:
    """
    Generates cross-references showing:
    - Which subroutines call a given subroutine (callers)
    - Which subroutines are called by a given subroutine (callees)
    - Call frequency statistics
    """
    
    def __init__(self) -> None:
        """Initialize the cross-referencer with empty tracking structures."""
        self.calls: Dict[int, List[int]] = {}  # {caller_addr: [callee_addr1, callee_addr2, ...]}
        self.called_by: Dict[int, List[int]] = {}  # {callee_addr: [caller_addr1, caller_addr2, ...]}
        self.call_counts: Dict[Tuple[int, int], int] = {}  # {(caller, callee): count}
        self.jump_targets: Dict[int, List[int]] = {}  # {target_addr: [source_addr1, source_addr2, ...]}
        self.branch_targets: Dict[int, List[int]] = {}  # {target_addr: [source_addr1, source_addr2, ...]}
        # Indirect dispatch: {target_cpu_addr: [dispatch_site_cpu_addr, ...]}
        # Populated by register_dispatch_targets() from split lo/hi table detection.
        self.dispatch_targets: Dict[int, List[int]] = {}
        
    def register_dispatch_targets(self, targets: Set[int], dispatch_site_cpu_addr: int) -> None:
        """
        Register indirect dispatch table targets found by the CPU simulator.
        
        These are addresses reached via JMP ($zp) where the pointer is loaded
        from split lo/hi ROM tables.  They show up in the xref summary as
        "Dispatched from: $XXXX (JMP indirect)" so the reader knows where
        each handler is invoked from.
        
        Args:
            targets: Set of CPU addresses that are dispatch table targets
            dispatch_site_cpu_addr: CPU address of the JMP ($zp) instruction
        """
        for target in targets:
            if target not in self.dispatch_targets:
                self.dispatch_targets[target] = []
            if dispatch_site_cpu_addr not in self.dispatch_targets[target]:
                self.dispatch_targets[target].append(dispatch_site_cpu_addr)
            # Also register as a jump_target so it appears in jump_targets xrefs
            if target not in self.jump_targets:
                self.jump_targets[target] = []
            if dispatch_site_cpu_addr not in self.jump_targets[target]:
                self.jump_targets[target].append(dispatch_site_cpu_addr)

    def analyze_references(self, rom: bytearray, code_addresses: Set[int], base_addr: int, labels: Dict[int, str]) -> None:
        """
        Analyze all JSR, JMP, and branch instructions to build cross-reference data.
        
        Args:
            rom: ROM data as bytearray
            code_addresses: Set of addresses identified as code
            base_addr: Base address where ROM is loaded in memory
            labels: Dictionary mapping addresses to label names
        """
        rom_size = len(rom)
        
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
            source_addr = base_addr + pc
            
            # Track JSR calls (subroutine calls)
            if mnemonic == 'JSR' and size == 3 and pc + 2 < rom_size:
                target_addr = rom[pc + 1] | (rom[pc + 2] << 8)
                
                if base_addr <= target_addr < base_addr + rom_size:
                    # Track caller -> callee relationship
                    if source_addr not in self.calls:
                        self.calls[source_addr] = []
                    self.calls[source_addr].append(target_addr)
                    
                    # Track callee -> callers relationship
                    if target_addr not in self.called_by:
                        self.called_by[target_addr] = []
                    self.called_by[target_addr].append(source_addr)
                    
                    # Track call frequency
                    call_pair = (source_addr, target_addr)
                    self.call_counts[call_pair] = self.call_counts.get(call_pair, 0) + 1
            
            # Track JMP targets
            elif mnemonic == 'JMP' and mode == 'absolute' and size == 3 and pc + 2 < rom_size:
                target_addr = rom[pc + 1] | (rom[pc + 2] << 8)
                
                if base_addr <= target_addr < base_addr + rom_size:
                    if target_addr not in self.jump_targets:
                        self.jump_targets[target_addr] = []
                    self.jump_targets[target_addr].append(source_addr)
            
            # Track branch targets
            elif mnemonic in ['BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ'] and pc + 2 < rom_size:
                offset = rom[pc + 1]
                if offset >= 128:
                    offset = offset - 256
                target_addr = (base_addr + pc + 2 + offset) & 0xFFFF
                
                if base_addr <= target_addr < base_addr + rom_size:
                    if target_addr not in self.branch_targets:
                        self.branch_targets[target_addr] = []
                    self.branch_targets[target_addr].append(source_addr)
            
            pc += size
    
    def get_callers(self, addr: int) -> List[int]:
        """
        Get list of addresses that call this subroutine.
        
        Args:
            addr: Subroutine address
            
        Returns:
            List of caller addresses
        """
        return self.called_by.get(addr, [])
    
    def get_callees(self, addr: int) -> List[int]:
        """
        Get list of addresses called by this subroutine.
        
        Args:
            addr: Subroutine address
            
        Returns:
            List of callee addresses
        """
        return self.calls.get(addr, [])
    
    def get_call_count(self, caller_addr: int, callee_addr: int) -> int:
        """
        Get number of times caller calls callee.
        
        Args:
            caller_addr: Address of calling subroutine
            callee_addr: Address of called subroutine
            
        Returns:
            Number of times this call occurs
        """
        return self.call_counts.get((caller_addr, callee_addr), 0)
    
    def generate_xref_comment(self, addr: int, labels: Dict[int, str], max_refs: int = 10) -> str:
        """
        Generate a cross-reference comment for a subroutine.
        
        Args:
            addr: Subroutine address
            labels: Dictionary mapping addresses to label names
            max_refs: Maximum number of references to show (default 10)
            
        Returns:
            Formatted comment string showing callers, or empty string if no callers
        """
        callers = self.get_callers(addr)
        
        if not callers:
            return ""
        
        # Sort callers by address
        callers = sorted(callers)
        
        # Limit to max_refs to avoid huge comments
        if len(callers) > max_refs:
            shown_callers = callers[:max_refs]
            remaining = len(callers) - max_refs
        else:
            shown_callers = callers
            remaining = 0
        
        # Use boxed style for consistency with old decompiler
        comment = "\n; ┌─────────────────────────────────────────────────┐\n"
        comment += "; │ Called by:                                      │\n"
        
        for caller in shown_callers:
            # Get label name if available
            if caller in labels:
                caller_name = labels[caller]
            else:
                caller_name = f"${caller:04X}"
            
            # Get call count
            count = self.get_call_count(caller, addr)
            if count > 1:
                caller_text = f"{caller_name} ({count}×)"
            else:
                caller_text = caller_name
            
            # Format with proper padding to fit in box (49 chars wide inside)
            caller_line = f"   {caller_text}"
            # Pad to 49 characters (box width minus borders)
            padded_line = f"{caller_line:<51}"
            comment += f"; │{padded_line}│\n"
        
        if remaining > 0:
            remaining_text = f"... and {remaining} more"
            remaining_line = f";   {remaining_text}"
            padded_line = f"{remaining_line:<51}"
            comment += f"; │{padded_line}│\n"
        
        comment += "; └─────────────────────────────────────────────────┘\n"
        
        return comment
    
    def generate_call_graph(self, labels, max_depth=3):
        """
        Generate a text-based call graph showing subroutine relationships.
        Returns a string representation of the call graph.
        """
        graph = "# Call Graph\n\n"
        
        # Find root subroutines (those not called by anyone, or called very rarely)
        all_callees = set(self.called_by.keys())
        all_callers = set(self.calls.keys())
        
        # Subroutines that are never called (entry points)
        roots = all_callers - all_callees
        
        # If no clear roots, use the most frequently calling subroutines
        if not roots:
            # Find subroutines with most outgoing calls
            call_counts = [(addr, len(callees)) for addr, callees in self.calls.items()]
            call_counts.sort(key=lambda x: x[1], reverse=True)
            roots = [addr for addr, _ in call_counts[:5]]  # Top 5
        
        # Generate graph for each root
        for root in sorted(roots):
            root_name = labels.get(root, f"${root:04X}")
            graph += f"\n## {root_name}\n"
            graph += self._generate_subtree(root, labels, depth=0, max_depth=max_depth, visited=set())
        
        return graph
    
    def _generate_subtree(self, addr, labels, depth, max_depth, visited):
        """Recursively generate call tree"""
        if depth >= max_depth or addr in visited:
            return ""
        
        visited.add(addr)
        indent = "  " * depth
        tree = ""
        
        callees = self.get_callees(addr)
        for callee in sorted(callees):
            callee_name = labels.get(callee, f"${callee:04X}")
            count = self.get_call_count(addr, callee)
            
            if count > 1:
                tree += f"{indent}├─ {callee_name} ({count}×)\n"
            else:
                tree += f"{indent}├─ {callee_name}\n"
            
            # Recurse
            tree += self._generate_subtree(callee, labels, depth + 1, max_depth, visited.copy())
        
        return tree
    
    def generate_statistics(self, labels):
        """
        Generate statistics about subroutine usage.
        """
        stats = "# Cross-Reference Statistics\n\n"
        
        # Total counts
        stats += f"Total subroutines: {len(set(self.calls.keys()) | set(self.called_by.keys()))}\n"
        stats += f"Total JSR calls: {sum(self.call_counts.values())}\n"
        stats += f"Total JMP targets: {len(self.jump_targets)}\n"
        stats += f"Total branch targets: {len(self.branch_targets)}\n\n"
        
        # Most called subroutines
        call_frequency = [(addr, len(callers)) for addr, callers in self.called_by.items()]
        call_frequency.sort(key=lambda x: x[1], reverse=True)
        
        stats += "## Most Called Subroutines\n"
        for addr, count in call_frequency[:10]:
            name = labels.get(addr, f"${addr:04X}")
            stats += f"  {name}: {count} callers\n"
        
        stats += "\n## Largest Subroutines (by callees)\n"
        callee_counts = [(addr, len(callees)) for addr, callees in self.calls.items()]
        callee_counts.sort(key=lambda x: x[1], reverse=True)
        
        for addr, count in callee_counts[:10]:
            name = labels.get(addr, f"${addr:04X}")
            stats += f"  {name}: calls {count} subroutines\n"
        
        # Leaf subroutines (call nothing)
        leaves = set(self.called_by.keys()) - set(self.calls.keys())
        stats += f"\n## Leaf Subroutines (call nothing): {len(leaves)}\n"
        for addr in sorted(leaves)[:10]:
            name = labels.get(addr, f"${addr:04X}")
            stats += f"  {name}\n"
        if len(leaves) > 10:
            stats += f"  ... and {len(leaves) - 10} more\n"
        
        return stats
    
    def get_reference_count(self, addr: int) -> int:
        """
        Get total number of references to this address (JSR + JMP + branches).
        
        Args:
            addr: Address to check
            
        Returns:
            Total reference count
        """
        count = 0
        count += len(self.called_by.get(addr, []))
        count += len(self.jump_targets.get(addr, []))
        count += len(self.branch_targets.get(addr, []))
        return count
    
    def is_dead_code(self, addr: int) -> bool:
        """
        Check if this address is never referenced (potential dead code).
        
        Args:
            addr: Address to check
            
        Returns:
            True if address has no references
        """
        return self.get_reference_count(addr) == 0


if __name__ == '__main__':
    print("Cross-Referencer - Generates call graphs and reference statistics")
    print("\nFeatures:")
    print("  - Tracks JSR (subroutine calls)")
    print("  - Tracks JMP (unconditional jumps)")
    print("  - Tracks branches (conditional jumps)")
    print("  - Generates call graphs")
    print("  - Identifies most/least used subroutines")
    print("  - Detects potential dead code")
    print("  - Tracks branches (conditional jumps)")

