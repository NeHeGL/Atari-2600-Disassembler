"""
Core Opcode Module - Consolidated opcode definitions and utilities

This module consolidates the following modules into a single file:
- opcodes.py: Complete 6502 opcode table (256 opcodes)
- opcode_flags.py: Processor flags and operation information
- opcode_reference.py: Addressing modes, categories, instruction details
- cycle_counter.py: CPU cycle counting and intelligent commenting
- opcode_lookup.py: CLI tool for opcode reference lookups

The 6507 (Atari 2600 CPU) is a stripped-down 6502 running at 1.19 MHz.
This module provides all opcode information needed for disassembly.
"""

import sys
from typing import Tuple, Optional

# ============================================================================
# OPCODE TABLE
# ============================================================================

OPCODES = {
    0x00: ('BRK', 1, 'implied'), 0x01: ('ORA', 2, 'indirect_x'), 0x05: ('ORA', 2, 'zeropage'),
    0x06: ('ASL', 2, 'zeropage'), 0x08: ('PHP', 1, 'implied'), 0x09: ('ORA', 2, 'immediate'),
    0x0A: ('ASL', 1, 'accumulator'), 0x0D: ('ORA', 3, 'absolute'), 0x0E: ('ASL', 3, 'absolute'),
    0x10: ('BPL', 2, 'relative'), 0x11: ('ORA', 2, 'indirect_y'), 0x15: ('ORA', 2, 'zeropage_x'),
    0x16: ('ASL', 2, 'zeropage_x'), 0x18: ('CLC', 1, 'implied'), 0x19: ('ORA', 3, 'absolute_y'),
    0x1D: ('ORA', 3, 'absolute_x'), 0x1E: ('ASL', 3, 'absolute_x'), 0x20: ('JSR', 3, 'absolute'),
    0x21: ('AND', 2, 'indirect_x'), 0x24: ('BIT', 2, 'zeropage'), 0x25: ('AND', 2, 'zeropage'),
    0x26: ('ROL', 2, 'zeropage'), 0x28: ('PLP', 1, 'implied'), 0x29: ('AND', 2, 'immediate'),
    0x2A: ('ROL', 1, 'accumulator'), 0x2C: ('BIT', 3, 'absolute'), 0x2D: ('AND', 3, 'absolute'),
    0x2E: ('ROL', 3, 'absolute'), 0x30: ('BMI', 2, 'relative'), 0x31: ('AND', 2, 'indirect_y'),
    0x35: ('AND', 2, 'zeropage_x'), 0x36: ('ROL', 2, 'zeropage_x'), 0x38: ('SEC', 1, 'implied'),
    0x39: ('AND', 3, 'absolute_y'), 0x3D: ('AND', 3, 'absolute_x'), 0x3E: ('ROL', 3, 'absolute_x'),
    0x40: ('RTI', 1, 'implied'), 0x41: ('EOR', 2, 'indirect_x'), 0x45: ('EOR', 2, 'zeropage'),
    0x46: ('LSR', 2, 'zeropage'), 0x48: ('PHA', 1, 'implied'), 0x49: ('EOR', 2, 'immediate'),
    0x4A: ('LSR', 1, 'accumulator'), 0x4C: ('JMP', 3, 'absolute'), 0x4D: ('EOR', 3, 'absolute'),
    0x4E: ('LSR', 3, 'absolute'), 0x50: ('BVC', 2, 'relative'), 0x51: ('EOR', 2, 'indirect_y'),
    0x55: ('EOR', 2, 'zeropage_x'), 0x56: ('LSR', 2, 'zeropage_x'), 0x58: ('CLI', 1, 'implied'),
    0x59: ('EOR', 3, 'absolute_y'), 0x5D: ('EOR', 3, 'absolute_x'), 0x5E: ('LSR', 3, 'absolute_x'),
    0x60: ('RTS', 1, 'implied'), 0x61: ('ADC', 2, 'indirect_x'), 0x65: ('ADC', 2, 'zeropage'),
    0x66: ('ROR', 2, 'zeropage'), 0x68: ('PLA', 1, 'implied'), 0x69: ('ADC', 2, 'immediate'),
    0x6A: ('ROR', 1, 'accumulator'), 0x6C: ('JMP', 3, 'indirect'), 0x6D: ('ADC', 3, 'absolute'),
    0x6E: ('ROR', 3, 'absolute'), 0x70: ('BVS', 2, 'relative'), 0x71: ('ADC', 2, 'indirect_y'),
    0x75: ('ADC', 2, 'zeropage_x'), 0x76: ('ROR', 2, 'zeropage_x'), 0x78: ('SEI', 1, 'implied'),
    0x79: ('ADC', 3, 'absolute_y'), 0x7D: ('ADC', 3, 'absolute_x'), 0x7E: ('ROR', 3, 'absolute_x'),
    0x81: ('STA', 2, 'indirect_x'), 0x84: ('STY', 2, 'zeropage'), 0x85: ('STA', 2, 'zeropage'),
    0x86: ('STX', 2, 'zeropage'), 0x88: ('DEY', 1, 'implied'), 0x8A: ('TXA', 1, 'implied'),
    0x8C: ('STY', 3, 'absolute'), 0x8D: ('STA', 3, 'absolute'), 0x8E: ('STX', 3, 'absolute'),
    0x90: ('BCC', 2, 'relative'), 0x91: ('STA', 2, 'indirect_y'), 0x94: ('STY', 2, 'zeropage_x'),
    0x95: ('STA', 2, 'zeropage_x'), 0x96: ('STX', 2, 'zeropage_y'), 0x98: ('TYA', 1, 'implied'),
    0x99: ('STA', 3, 'absolute_y'), 0x9A: ('TXS', 1, 'implied'), 0x9D: ('STA', 3, 'absolute_x'),
    0xA0: ('LDY', 2, 'immediate'), 0xA1: ('LDA', 2, 'indirect_x'), 0xA2: ('LDX', 2, 'immediate'),
    0xA4: ('LDY', 2, 'zeropage'), 0xA5: ('LDA', 2, 'zeropage'), 0xA6: ('LDX', 2, 'zeropage'),
    0xA8: ('TAY', 1, 'implied'), 0xA9: ('LDA', 2, 'immediate'), 0xAA: ('TAX', 1, 'implied'),
    0xAC: ('LDY', 3, 'absolute'), 0xAD: ('LDA', 3, 'absolute'), 0xAE: ('LDX', 3, 'absolute'),
    0xB0: ('BCS', 2, 'relative'), 0xB1: ('LDA', 2, 'indirect_y'), 0xB4: ('LDY', 2, 'zeropage_x'),
    0xB5: ('LDA', 2, 'zeropage_x'), 0xB6: ('LDX', 2, 'zeropage_y'), 0xB8: ('CLV', 1, 'implied'),
    0xB9: ('LDA', 3, 'absolute_y'), 0xBA: ('TSX', 1, 'implied'), 0xBC: ('LDY', 3, 'absolute_x'),
    0xBD: ('LDA', 3, 'absolute_x'), 0xBE: ('LDX', 3, 'absolute_y'), 0xC0: ('CPY', 2, 'immediate'),
    0xC1: ('CMP', 2, 'indirect_x'), 0xC4: ('CPY', 2, 'zeropage'), 0xC5: ('CMP', 2, 'zeropage'),
    0xC6: ('DEC', 2, 'zeropage'), 0xC8: ('INY', 1, 'implied'), 0xC9: ('CMP', 2, 'immediate'),
    0xCA: ('DEX', 1, 'implied'), 0xCC: ('CPY', 3, 'absolute'), 0xCD: ('CMP', 3, 'absolute'),
    0xCE: ('DEC', 3, 'absolute'), 0xD0: ('BNE', 2, 'relative'), 0xD1: ('CMP', 2, 'indirect_y'),
    0xD5: ('CMP', 2, 'zeropage_x'), 0xD6: ('DEC', 2, 'zeropage_x'), 0xD8: ('CLD', 1, 'implied'),
    0xD9: ('CMP', 3, 'absolute_y'), 0xDD: ('CMP', 3, 'absolute_x'), 0xDE: ('DEC', 3, 'absolute_x'),
    0xE0: ('CPX', 2, 'immediate'), 0xE1: ('SBC', 2, 'indirect_x'), 0xE4: ('CPX', 2, 'zeropage'),
    0xE5: ('SBC', 2, 'zeropage'), 0xE6: ('INC', 2, 'zeropage'), 0xE8: ('INX', 1, 'implied'),
    0xE9: ('SBC', 2, 'immediate'), 0xEA: ('NOP', 1, 'implied'), 0xEC: ('CPX', 3, 'absolute'),
    0xED: ('SBC', 3, 'absolute'), 0xEE: ('INC', 3, 'absolute'), 0xF0: ('BEQ', 2, 'relative'),
    0xF1: ('SBC', 2, 'indirect_y'), 0xF5: ('SBC', 2, 'zeropage_x'), 0xF6: ('INC', 2, 'zeropage_x'),
    0xF8: ('SED', 1, 'implied'), 0xF9: ('SBC', 3, 'absolute_y'), 0xFD: ('SBC', 3, 'absolute_x'),
    0xFE: ('INC', 3, 'absolute_x'),
    # Illegal/Undocumented Opcodes
    0x02: ('NOP', 1, 'implied'), 0x03: ('SLO', 2, 'indirect_x'), 0x04: ('NOP', 2, 'zeropage'),
    0x07: ('SLO', 2, 'zeropage'), 0x0B: ('ANC', 2, 'immediate'), 0x0C: ('NOP', 3, 'absolute'),
    0x0F: ('SLO', 3, 'absolute'), 0x12: ('NOP', 1, 'implied'), 0x13: ('SLO', 2, 'indirect_y'),
    0x14: ('NOP', 2, 'zeropage_x'), 0x17: ('SLO', 2, 'zeropage_x'), 0x1A: ('NOP', 1, 'implied'),
    0x1B: ('SLO', 3, 'absolute_y'), 0x1C: ('NOP', 3, 'absolute_x'), 0x1F: ('SLO', 3, 'absolute_x'),
    0x22: ('NOP', 1, 'implied'), 0x23: ('RLA', 2, 'indirect_x'), 0x27: ('RLA', 2, 'zeropage'),
    0x2B: ('ANC', 2, 'immediate'), 0x2F: ('RLA', 3, 'absolute'), 0x32: ('NOP', 1, 'implied'),
    0x33: ('RLA', 2, 'indirect_y'), 0x34: ('NOP', 2, 'zeropage_x'), 0x37: ('RLA', 2, 'zeropage_x'),
    0x3A: ('NOP', 1, 'implied'), 0x3B: ('RLA', 3, 'absolute_y'), 0x3C: ('NOP', 3, 'absolute_x'),
    0x3F: ('RLA', 3, 'absolute_x'), 0x42: ('NOP', 1, 'implied'), 0x43: ('SRE', 2, 'indirect_x'),
    0x44: ('NOP', 2, 'zeropage'), 0x47: ('SRE', 2, 'zeropage'), 0x4B: ('ALR', 2, 'immediate'),
    0x4F: ('SRE', 3, 'absolute'), 0x52: ('NOP', 1, 'implied'), 0x53: ('SRE', 2, 'indirect_y'),
    0x54: ('NOP', 2, 'zeropage_x'), 0x57: ('SRE', 2, 'zeropage_x'), 0x5A: ('NOP', 1, 'implied'),
    0x5B: ('SRE', 3, 'absolute_y'), 0x5C: ('NOP', 3, 'absolute_x'), 0x5F: ('SRE', 3, 'absolute_x'),
    0x62: ('NOP', 1, 'implied'), 0x63: ('RRA', 2, 'indirect_x'), 0x64: ('NOP', 2, 'zeropage'),
    0x67: ('RRA', 2, 'zeropage'), 0x6B: ('ARR', 2, 'immediate'), 0x6F: ('RRA', 3, 'absolute'),
    0x72: ('NOP', 1, 'implied'), 0x73: ('RRA', 2, 'indirect_y'), 0x74: ('NOP', 2, 'zeropage_x'),
    0x77: ('RRA', 2, 'zeropage_x'), 0x7A: ('NOP', 1, 'implied'), 0x7B: ('RRA', 3, 'absolute_y'),
    0x7C: ('NOP', 3, 'absolute_x'), 0x7F: ('RRA', 3, 'absolute_x'), 0x80: ('NOP', 2, 'immediate'),
    0x82: ('NOP', 2, 'immediate'), 0x83: ('SAX', 2, 'indirect_x'), 0x87: ('SAX', 2, 'zeropage'),
    0x89: ('NOP', 2, 'immediate'), 0x8B: ('XAA', 2, 'immediate'), 0x8F: ('SAX', 3, 'absolute'),
    0x92: ('NOP', 1, 'implied'), 0x93: ('AHX', 2, 'indirect_y'), 0x97: ('SAX', 2, 'zeropage_y'),
    0x9B: ('TAS', 3, 'absolute_y'), 0x9C: ('SHY', 3, 'absolute_x'), 0x9E: ('SHX', 3, 'absolute_y'),
    0x9F: ('AHX', 3, 'absolute_y'), 0xA3: ('LAX', 2, 'indirect_x'), 0xA7: ('LAX', 2, 'zeropage'),
    0xAB: ('LAX', 2, 'immediate'), 0xAF: ('LAX', 3, 'absolute'), 0xB2: ('NOP', 1, 'implied'),
    0xB3: ('LAX', 2, 'indirect_y'), 0xB7: ('LAX', 2, 'zeropage_y'), 0xBB: ('LAS', 3, 'absolute_y'),
    0xBF: ('LAX', 3, 'absolute_y'), 0xC2: ('NOP', 2, 'immediate'), 0xC3: ('DCP', 2, 'indirect_x'),
    0xC7: ('DCP', 2, 'zeropage'), 0xCB: ('AXS', 2, 'immediate'), 0xCF: ('DCP', 3, 'absolute'),
    0xD2: ('NOP', 1, 'implied'), 0xD3: ('DCP', 2, 'indirect_y'), 0xD4: ('NOP', 2, 'zeropage_x'),
    0xD7: ('DCP', 2, 'zeropage_x'), 0xDA: ('NOP', 1, 'implied'), 0xDB: ('DCP', 3, 'absolute_y'),
    0xDC: ('NOP', 3, 'absolute_x'), 0xDF: ('DCP', 3, 'absolute_x'), 0xE2: ('NOP', 2, 'immediate'),
    0xE3: ('ISC', 2, 'indirect_x'), 0xE7: ('ISC', 2, 'zeropage'), 0xEB: ('SBC', 2, 'immediate'),
    0xEF: ('ISC', 3, 'absolute'), 0xF2: ('NOP', 1, 'implied'), 0xF3: ('ISC', 2, 'indirect_y'),
    0xF4: ('NOP', 2, 'zeropage_x'), 0xF7: ('ISC', 2, 'zeropage_x'), 0xFA: ('NOP', 1, 'implied'),
    0xFB: ('ISC', 3, 'absolute_y'), 0xFC: ('NOP', 3, 'absolute_x'), 0xFF: ('ISC', 3, 'absolute_x'),
}

# ============================================================================
# PROCESSOR FLAGS AND OPERATIONS
# ============================================================================


# Flags affected by each mnemonic
# Format: 'mnemonic': 'flags_affected'
OPCODE_FLAGS = {
    # Load/Store - affect N and Z
    'LDA': 'NZ', 'LDX': 'NZ', 'LDY': 'NZ',
    'STA': '', 'STX': '', 'STY': '',
    
    # Arithmetic - affect N, V, Z, C
    'ADC': 'NVZC', 'SBC': 'NVZC',
    
    # Increment/Decrement - affect N and Z
    'INC': 'NZ', 'INX': 'NZ', 'INY': 'NZ',
    'DEC': 'NZ', 'DEX': 'NZ', 'DEY': 'NZ',
    
    # Logical operations - affect N and Z
    'AND': 'NZ', 'ORA': 'NZ', 'EOR': 'NZ',
    
    # Shift/Rotate - affect N, Z, C
    'ASL': 'NZC', 'LSR': 'NZC',
    'ROL': 'NZC', 'ROR': 'NZC',
    
    # Compare - affect N, Z, C
    'CMP': 'NZC', 'CPX': 'NZC', 'CPY': 'NZC',
    
    # Bit test - affects N (bit 7), V (bit 6), Z
    'BIT': 'NVZ',
    
    # Transfers - affect N and Z
    'TAX': 'NZ', 'TAY': 'NZ', 'TXA': 'NZ', 'TYA': 'NZ',
    'TSX': 'NZ', 'TXS': '',
    
    # Stack operations
    'PHA': '', 'PHP': '',
    'PLA': 'NZ', 'PLP': 'NVBDIZC',  # PLP restores all flags
    
    # Flag operations
    'CLC': 'C', 'SEC': 'C',
    'CLI': 'I', 'SEI': 'I',
    'CLV': 'V',
    'CLD': 'D', 'SED': 'D',
    
    # Control flow
    'JMP': '', 'JSR': '', 'RTS': '', 'RTI': 'NVBDIZC',  # RTI restores all flags
    'BRK': 'BI',  # Sets B and I flags
    
    # Branches - don't affect flags
    'BPL': '', 'BMI': '', 'BVC': '', 'BVS': '',
    'BCC': '', 'BCS': '', 'BNE': '', 'BEQ': '',
    
    # No operation
    'NOP': '',
    
    # Illegal opcodes
    'SLO': 'NZC',  # ASL + ORA
    'RLA': 'NZC',  # ROL + AND
    'SRE': 'NZC',  # LSR + EOR
    'RRA': 'NVZC', # ROR + ADC
    'SAX': '',     # Store A AND X
    'LAX': 'NZ',   # Load A and X
    'DCP': 'NZC',  # DEC + CMP
    'ISC': 'NVZC', # INC + SBC
    'ANC': 'NZC',  # AND + set carry
    'ALR': 'NZC',  # AND + LSR
    'ARR': 'NVZC', # AND + ROR
    'XAA': 'NZ',   # Unstable
    'AHX': '',     # Store A AND X AND (H+1)
    'TAS': '',     # Transfer A AND X to S
    'SHY': '',     # Store Y AND (H+1)
    'SHX': '',     # Store X AND (H+1)
    'LAS': 'NZ',   # Load A, X, S
    'AXS': 'NZC',  # (A AND X) - immediate
}

# Operation descriptions for each mnemonic
OPCODE_OPERATIONS = {
    # Load/Store
    'LDA': 'A = M',
    'LDX': 'X = M',
    'LDY': 'Y = M',
    'STA': 'M = A',
    'STX': 'M = X',
    'STY': 'M = Y',
    
    # Arithmetic
    'ADC': 'A = A + M + C',
    'SBC': 'A = A - M - (1-C)',
    
    # Increment/Decrement
    'INC': 'M = M + 1',
    'INX': 'X = X + 1',
    'INY': 'Y = Y + 1',
    'DEC': 'M = M - 1',
    'DEX': 'X = X - 1',
    'DEY': 'Y = Y - 1',
    
    # Logical
    'AND': 'A = A & M',
    'ORA': 'A = A | M',
    'EOR': 'A = A ^ M',
    
    # Shift/Rotate
    'ASL': 'C <- [76543210] <- 0',
    'LSR': '0 -> [76543210] -> C',
    'ROL': 'C <- [76543210] <- C',
    'ROR': 'C -> [76543210] -> C',
    
    # Compare
    'CMP': 'A - M',
    'CPX': 'X - M',
    'CPY': 'Y - M',
    
    # Bit test
    'BIT': 'A & M (sets N=M7, V=M6, Z)',
    
    # Transfers
    'TAX': 'X = A',
    'TAY': 'Y = A',
    'TXA': 'A = X',
    'TYA': 'A = Y',
    'TSX': 'X = S',
    'TXS': 'S = X',
    
    # Stack
    'PHA': 'Push A',
    'PHP': 'Push P',
    'PLA': 'Pull A',
    'PLP': 'Pull P',
    
    # Flags
    'CLC': 'C = 0',
    'SEC': 'C = 1',
    'CLI': 'I = 0',
    'SEI': 'I = 1',
    'CLV': 'V = 0',
    'CLD': 'D = 0',
    'SED': 'D = 1',
    
    # Control
    'JMP': 'PC = addr',
    'JSR': 'Push PC+2, PC = addr',
    'RTS': 'Pull PC, PC = PC+1',
    'RTI': 'Pull P, Pull PC',
    'BRK': 'Push PC+2, Push P, PC = ($FFFE)',
    
    # Branches
    'BPL': 'Branch if N = 0',
    'BMI': 'Branch if N = 1',
    'BVC': 'Branch if V = 0',
    'BVS': 'Branch if V = 1',
    'BCC': 'Branch if C = 0',
    'BCS': 'Branch if C = 1',
    'BNE': 'Branch if Z = 0',
    'BEQ': 'Branch if Z = 1',
    
    # No operation
    'NOP': 'No operation',
    
    # Illegal opcodes
    'SLO': 'M = M << 1, A = A | M',
    'RLA': 'M = M rol 1, A = A & M',
    'SRE': 'M = M >> 1, A = A ^ M',
    'RRA': 'M = M ror 1, A = A + M + C',
    'SAX': 'M = A & X',
    'LAX': 'A = X = M',
    'DCP': 'M = M - 1, A - M',
    'ISC': 'M = M + 1, A = A - M - (1-C)',
    'ANC': 'A = A & M, C = N',
    'ALR': 'A = (A & M) >> 1',
    'ARR': 'A = (A & M) ror 1',
    'XAA': 'A = X & M (unstable)',
    'AHX': 'M = A & X & (H+1)',
    'TAS': 'S = A & X, M = S & (H+1)',
    'SHY': 'M = Y & (H+1)',
    'SHX': 'M = X & (H+1)',
    'LAS': 'A = X = S = M & S',
    'AXS': 'X = (A & X) - M',
}

def get_opcode_flags(mnemonic: str) -> str:
    """
    Get processor flags affected by an instruction.
    
    Args:
        mnemonic: Instruction mnemonic (e.g., 'LDA', 'STA')
        
    Returns:
        String of flags affected (e.g., 'NZ', 'NVZC', '')
    """
    return OPCODE_FLAGS.get(mnemonic, '')

def get_opcode_operation(mnemonic: str) -> str:
    """
    Get operation description for an instruction.
    
    Args:
        mnemonic: Instruction mnemonic (e.g., 'LDA', 'ADC')
        
    Returns:
        Operation description (e.g., 'A = M', 'A = A + M + C')
    """
    return OPCODE_OPERATIONS.get(mnemonic, '')

def format_flags_comment(mnemonic: str) -> str:
    """
    Format flags as a comment string.
    
    Args:
        mnemonic: Instruction mnemonic
        
    Returns:
        Formatted comment like "Flags: N Z" or empty string if no flags
    """
    flags = get_opcode_flags(mnemonic)
    if flags:
        # Add spaces between flag letters for readability
        spaced_flags = ' '.join(flags)
        return f"Flags: {spaced_flags}"
    return ""

def format_operation_comment(mnemonic: str) -> str:
    """
    Format operation as a comment string.
    
    Args:
        mnemonic: Instruction mnemonic
        
    Returns:
        Operation description or empty string
    """
    return get_opcode_operation(mnemonic)


# ============================================================================
# ADDRESSING MODES AND INSTRUCTION REFERENCE
# ============================================================================


# Addressing mode descriptions
ADDRESSING_MODES = {
    'implied': {
        'syntax': '',
        'description': 'Operand implied',
        'example': 'NOP'
    },
    'accumulator': {
        'syntax': 'A',
        'description': 'Operate on accumulator',
        'example': 'ASL A'
    },
    'immediate': {
        'syntax': '#$nn',
        'description': 'Use immediate value',
        'example': 'LDA #$00'
    },
    'zeropage': {
        'syntax': '$nn',
        'description': 'Zero page address (0x00-0xFF)',
        'example': 'LDA $80'
    },
    'zeropage_x': {
        'syntax': '$nn,X',
        'description': 'Zero page indexed with X',
        'example': 'LDA $80,X'
    },
    'zeropage_y': {
        'syntax': '$nn,Y',
        'description': 'Zero page indexed with Y',
        'example': 'LDX $80,Y'
    },
    'absolute': {
        'syntax': '$nnnn',
        'description': 'Absolute address',
        'example': 'JMP $F000'
    },
    'absolute_x': {
        'syntax': '$nnnn,X',
        'description': 'Absolute address indexed with X',
        'example': 'LDA $1000,X'
    },
    'absolute_y': {
        'syntax': '$nnnn,Y',
        'description': 'Absolute address indexed with Y',
        'example': 'LDA $1000,Y'
    },
    'indirect': {
        'syntax': '($nnnn)',
        'description': 'Indirect address (JMP only)',
        'example': 'JMP ($FFFC)'
    },
    'indirect_x': {
        'syntax': '($nn,X)',
        'description': 'Indexed indirect (pre-indexed)',
        'example': 'LDA ($80,X)'
    },
    'indirect_y': {
        'syntax': '($nn),Y',
        'description': 'Indirect indexed (post-indexed)',
        'example': 'LDA ($80),Y'
    },
    'relative': {
        'syntax': 'label',
        'description': 'Relative branch (-128 to +127)',
        'example': 'BNE Loop'
    }
}

# Instruction categories
INSTRUCTION_CATEGORIES = {
    'LOAD_STORE': ['LDA', 'LDX', 'LDY', 'STA', 'STX', 'STY'],
    'TRANSFER': ['TAX', 'TAY', 'TXA', 'TYA', 'TSX', 'TXS'],
    'STACK': ['PHA', 'PHP', 'PLA', 'PLP'],
    'ARITHMETIC': ['ADC', 'SBC', 'INC', 'INX', 'INY', 'DEC', 'DEX', 'DEY'],
    'LOGICAL': ['AND', 'ORA', 'EOR', 'BIT'],
    'SHIFT': ['ASL', 'LSR', 'ROL', 'ROR'],
    'COMPARE': ['CMP', 'CPX', 'CPY'],
    'BRANCH': ['BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ'],
    'JUMP': ['JMP', 'JSR', 'RTS', 'RTI'],
    'FLAGS': ['CLC', 'SEC', 'CLI', 'SEI', 'CLV', 'CLD', 'SED'],
    'SYSTEM': ['BRK', 'NOP'],
    'ILLEGAL': ['SLO', 'RLA', 'SRE', 'RRA', 'SAX', 'LAX', 'DCP', 'ISC',
                'ANC', 'ALR', 'ARR', 'XAA', 'AHX', 'TAS', 'SHY', 'SHX', 'LAS', 'AXS']
}

# Detailed instruction descriptions
INSTRUCTION_DETAILS = {
    # Load/Store
    'LDA': {
        'name': 'Load Accumulator',
        'description': 'Loads a byte of memory into the accumulator',
        'operation': 'A = M',
        'flags': 'N Z',
        'notes': 'Sets N if bit 7 is set, Z if A = 0'
    },
    'LDX': {
        'name': 'Load X Register',
        'description': 'Loads a byte of memory into the X register',
        'operation': 'X = M',
        'flags': 'N Z',
        'notes': 'Sets N if bit 7 is set, Z if X = 0'
    },
    'LDY': {
        'name': 'Load Y Register',
        'description': 'Loads a byte of memory into the Y register',
        'operation': 'Y = M',
        'flags': 'N Z',
        'notes': 'Sets N if bit 7 is set, Z if Y = 0'
    },
    'STA': {
        'name': 'Store Accumulator',
        'description': 'Stores the accumulator in memory',
        'operation': 'M = A',
        'flags': '',
        'notes': 'No flags affected'
    },
    'STX': {
        'name': 'Store X Register',
        'description': 'Stores the X register in memory',
        'operation': 'M = X',
        'flags': '',
        'notes': 'No flags affected'
    },
    'STY': {
        'name': 'Store Y Register',
        'description': 'Stores the Y register in memory',
        'operation': 'M = Y',
        'flags': '',
        'notes': 'No flags affected'
    },
    
    # Arithmetic
    'ADC': {
        'name': 'Add with Carry',
        'description': 'Adds memory to accumulator with carry',
        'operation': 'A = A + M + C',
        'flags': 'N V Z C',
        'notes': 'V set on signed overflow, C set on unsigned overflow'
    },
    'SBC': {
        'name': 'Subtract with Carry',
        'description': 'Subtracts memory from accumulator with borrow',
        'operation': 'A = A - M - (1-C)',
        'flags': 'N V Z C',
        'notes': 'V set on signed overflow, C clear on borrow'
    },
    'INC': {
        'name': 'Increment Memory',
        'description': 'Increments memory by one',
        'operation': 'M = M + 1',
        'flags': 'N Z',
        'notes': 'Does not affect carry flag'
    },
    'DEC': {
        'name': 'Decrement Memory',
        'description': 'Decrements memory by one',
        'operation': 'M = M - 1',
        'flags': 'N Z',
        'notes': 'Does not affect carry flag'
    },
    
    # Logical
    'AND': {
        'name': 'Logical AND',
        'description': 'Performs bitwise AND with accumulator',
        'operation': 'A = A & M',
        'flags': 'N Z',
        'notes': 'Used for masking bits'
    },
    'ORA': {
        'name': 'Logical OR',
        'description': 'Performs bitwise OR with accumulator',
        'operation': 'A = A | M',
        'flags': 'N Z',
        'notes': 'Used for setting bits'
    },
    'EOR': {
        'name': 'Exclusive OR',
        'description': 'Performs bitwise XOR with accumulator',
        'operation': 'A = A ^ M',
        'flags': 'N Z',
        'notes': 'Used for toggling bits'
    },
    'BIT': {
        'name': 'Bit Test',
        'description': 'Tests bits in memory with accumulator',
        'operation': 'A & M',
        'flags': 'N V Z',
        'notes': 'N = bit 7 of M, V = bit 6 of M, Z = (A & M) == 0'
    },
    
    # Shift/Rotate
    'ASL': {
        'name': 'Arithmetic Shift Left',
        'description': 'Shifts all bits left one position',
        'operation': 'C <- [76543210] <- 0',
        'flags': 'N Z C',
        'notes': 'Bit 7 goes to carry, 0 enters bit 0'
    },
    'LSR': {
        'name': 'Logical Shift Right',
        'description': 'Shifts all bits right one position',
        'operation': '0 -> [76543210] -> C',
        'flags': 'N Z C',
        'notes': 'Bit 0 goes to carry, 0 enters bit 7, N always clear'
    },
    'ROL': {
        'name': 'Rotate Left',
        'description': 'Rotates all bits left one position through carry',
        'operation': 'C <- [76543210] <- C',
        'flags': 'N Z C',
        'notes': 'Bit 7 to carry, carry to bit 0'
    },
    'ROR': {
        'name': 'Rotate Right',
        'description': 'Rotates all bits right one position through carry',
        'operation': 'C -> [76543210] -> C',
        'flags': 'N Z C',
        'notes': 'Bit 0 to carry, carry to bit 7'
    },
    
    # Branches
    'BPL': {
        'name': 'Branch if Plus',
        'description': 'Branch if negative flag is clear',
        'operation': 'if N = 0, PC = PC + offset',
        'flags': '',
        'notes': 'Tests result of arithmetic/logic operations'
    },
    'BMI': {
        'name': 'Branch if Minus',
        'description': 'Branch if negative flag is set',
        'operation': 'if N = 1, PC = PC + offset',
        'flags': '',
        'notes': 'Tests result of arithmetic/logic operations'
    },
    'BVC': {
        'name': 'Branch if Overflow Clear',
        'description': 'Branch if overflow flag is clear',
        'operation': 'if V = 0, PC = PC + offset',
        'flags': '',
        'notes': 'Tests for valid signed arithmetic result'
    },
    'BVS': {
        'name': 'Branch if Overflow Set',
        'description': 'Branch if overflow flag is set',
        'operation': 'if V = 1, PC = PC + offset',
        'flags': '',
        'notes': 'Tests for signed arithmetic overflow'
    },
    'BCC': {
        'name': 'Branch if Carry Clear',
        'description': 'Branch if carry flag is clear',
        'operation': 'if C = 0, PC = PC + offset',
        'flags': '',
        'notes': 'Also known as BLT (branch if less than) for unsigned'
    },
    'BCS': {
        'name': 'Branch if Carry Set',
        'description': 'Branch if carry flag is set',
        'operation': 'if C = 1, PC = PC + offset',
        'flags': '',
        'notes': 'Also known as BGE (branch if greater/equal) for unsigned'
    },
    'BNE': {
        'name': 'Branch if Not Equal',
        'description': 'Branch if zero flag is clear',
        'operation': 'if Z = 0, PC = PC + offset',
        'flags': '',
        'notes': 'Most common branch, used after CMP'
    },
    'BEQ': {
        'name': 'Branch if Equal',
        'description': 'Branch if zero flag is set',
        'operation': 'if Z = 1, PC = PC + offset',
        'flags': '',
        'notes': 'Used after CMP or to test for zero'
    },
    
    # Illegal opcodes
    'SLO': {
        'name': 'Shift Left then OR',
        'description': 'ASL memory then OR with accumulator (illegal)',
        'operation': 'M = M << 1, A = A | M',
        'flags': 'N Z C',
        'notes': 'Combines ASL and ORA in one instruction'
    },
    'RLA': {
        'name': 'Rotate Left then AND',
        'description': 'ROL memory then AND with accumulator (illegal)',
        'operation': 'M = M rol 1, A = A & M',
        'flags': 'N Z C',
        'notes': 'Combines ROL and AND in one instruction'
    },
    'LAX': {
        'name': 'Load A and X',
        'description': 'Load accumulator and X register (illegal)',
        'operation': 'A = X = M',
        'flags': 'N Z',
        'notes': 'Loads both A and X with same value'
    },
    'SAX': {
        'name': 'Store A AND X',
        'description': 'Store A AND X in memory (illegal)',
        'operation': 'M = A & X',
        'flags': '',
        'notes': 'Stores bitwise AND of A and X'
    },
}

def get_instruction_category(mnemonic: str) -> str:
    """Get the category for an instruction."""
    for category, mnemonics in INSTRUCTION_CATEGORIES.items():
        if mnemonic in mnemonics:
            return category.replace('_', ' ').title()
    return 'Unknown'

def get_instruction_info(mnemonic: str) -> dict:
    """Get detailed information about an instruction."""
    return INSTRUCTION_DETAILS.get(mnemonic, {
        'name': mnemonic,
        'description': 'Unknown instruction',
        'operation': '',
        'flags': '',
        'notes': ''
    })

def get_addressing_mode_info(mode: str) -> dict:
    """Get information about an addressing mode."""
    return ADDRESSING_MODES.get(mode, {
        'syntax': '',
        'description': 'Unknown addressing mode',
        'example': ''
    })


# ============================================================================
# CYCLE COUNTING AND TIMING
# ============================================================================


from typing import Tuple, Optional

# Timing constants
CPU_FREQUENCY_MHZ = 1.19
CYCLES_PER_SCANLINE = 76

# Cycle counts for each opcode (base cycles)
CYCLE_COUNTS = {
    # ADC
    0x69: 2, 0x65: 3, 0x75: 4, 0x6D: 4, 0x7D: 4, 0x79: 4, 0x61: 6, 0x71: 5,
    # AND  
    0x29: 2, 0x25: 3, 0x35: 4, 0x2D: 4, 0x3D: 4, 0x39: 4, 0x21: 6, 0x31: 5,
    # ASL
    0x0A: 2, 0x06: 5, 0x16: 6, 0x0E: 6, 0x1E: 7,
    # Branch instructions
    0x90: 2, 0xB0: 2, 0xF0: 2, 0x30: 2, 0xD0: 2, 0x10: 2, 0x50: 2, 0x70: 2,
    # BIT
    0x24: 3, 0x2C: 4,
    # BRK
    0x00: 7,
    # Clear flags
    0x18: 2, 0xD8: 2, 0x58: 2, 0xB8: 2,
    # CMP
    0xC9: 2, 0xC5: 3, 0xD5: 4, 0xCD: 4, 0xDD: 4, 0xD9: 4, 0xC1: 6, 0xD1: 5,
    # CPX
    0xE0: 2, 0xE4: 3, 0xEC: 4,
    # CPY
    0xC0: 2, 0xC4: 3, 0xCC: 4,
    # DEC
    0xC6: 5, 0xD6: 6, 0xCE: 6, 0xDE: 7,
    # DEX, DEY
    0xCA: 2, 0x88: 2,
    # EOR
    0x49: 2, 0x45: 3, 0x55: 4, 0x4D: 4, 0x5D: 4, 0x59: 4, 0x41: 6, 0x51: 5,
    # INC
    0xE6: 5, 0xF6: 6, 0xEE: 6, 0xFE: 7,
    # INX, INY
    0xE8: 2, 0xC8: 2,
    # JMP
    0x4C: 3, 0x6C: 5,
    # JSR
    0x20: 6,
    # LDA
    0xA9: 2, 0xA5: 3, 0xB5: 4, 0xAD: 4, 0xBD: 4, 0xB9: 4, 0xA1: 6, 0xB1: 5,
    # LDX
    0xA2: 2, 0xA6: 3, 0xB6: 4, 0xAE: 4, 0xBE: 4,
    # LDY
    0xA0: 2, 0xA4: 3, 0xB4: 4, 0xAC: 4, 0xBC: 4,
    # LSR
    0x4A: 2, 0x46: 5, 0x56: 6, 0x4E: 6, 0x5E: 7,
    # NOP
    0xEA: 2,
    # ORA
    0x09: 2, 0x05: 3, 0x15: 4, 0x0D: 4, 0x1D: 4, 0x19: 4, 0x01: 6, 0x11: 5,
    # Stack operations
    0x48: 3, 0x08: 3, 0x68: 4, 0x28: 4,
    # ROL
    0x2A: 2, 0x26: 5, 0x36: 6, 0x2E: 6, 0x3E: 7,
    # ROR
    0x6A: 2, 0x66: 5, 0x76: 6, 0x6E: 6, 0x7E: 7,
    # RTI, RTS
    0x40: 6, 0x60: 6,
    # SBC
    0xE9: 2, 0xE5: 3, 0xF5: 4, 0xED: 4, 0xFD: 4, 0xF9: 4, 0xE1: 6, 0xF1: 5,
    # Set flags
    0x38: 2, 0xF8: 2, 0x78: 2,
    # STA
    0x85: 3, 0x95: 4, 0x8D: 4, 0x9D: 5, 0x99: 5, 0x81: 6, 0x91: 6,
    # STX
    0x86: 3, 0x96: 4, 0x8E: 4,
    # STY
    0x84: 3, 0x94: 4, 0x8C: 4,
    # Transfers
    0xAA: 2, 0xA8: 2, 0xBA: 2, 0x8A: 2, 0x9A: 2, 0x98: 2,
    
    # Illegal/Undocumented Opcodes
    # SLO (ASL + ORA)
    0x03: 8, 0x07: 5, 0x0F: 6, 0x13: 8, 0x17: 6, 0x1B: 7, 0x1F: 7,
    # RLA (ROL + AND)
    0x23: 8, 0x27: 5, 0x2F: 6, 0x33: 8, 0x37: 6, 0x3B: 7, 0x3F: 7,
    # SRE (LSR + EOR)
    0x43: 8, 0x47: 5, 0x4F: 6, 0x53: 8, 0x57: 6, 0x5B: 7, 0x5F: 7,
    # RRA (ROR + ADC)
    0x63: 8, 0x67: 5, 0x6F: 6, 0x73: 8, 0x77: 6, 0x7B: 7, 0x7F: 7,
    # SAX (Store A AND X)
    0x83: 6, 0x87: 3, 0x8F: 4, 0x97: 4,
    # LAX (Load A and X)
    0xA3: 6, 0xA7: 3, 0xAF: 4, 0xB3: 5, 0xB7: 4, 0xBF: 4, 0xAB: 2,
    # DCP (DEC + CMP)
    0xC3: 8, 0xC7: 5, 0xCF: 6, 0xD3: 8, 0xD7: 6, 0xDB: 7, 0xDF: 7,
    # ISC (INC + SBC)
    0xE3: 8, 0xE7: 5, 0xEF: 6, 0xF3: 8, 0xF7: 6, 0xFB: 7, 0xFF: 7,
    # ANC (AND + set carry)
    0x0B: 2, 0x2B: 2,
    # ALR (AND + LSR)
    0x4B: 2,
    # ARR (AND + ROR)
    0x6B: 2,
    # AXS ((A AND X) - immediate)
    0xCB: 2,
    # Unstable/highly illegal opcodes
    0x8B: 2,  # XAA
    0x93: 6,  # AHX indirect_y
    0x9B: 5,  # TAS
    0x9C: 5,  # SHY
    0x9E: 5,  # SHX
    0x9F: 5,  # AHX absolute_y
    0xBB: 4,  # LAS
    # Illegal NOPs with various cycle counts
    0x02: 2, 0x12: 2, 0x22: 2, 0x32: 2, 0x42: 2, 0x52: 2, 0x62: 2, 0x72: 2,
    0x92: 2, 0xB2: 2, 0xD2: 2, 0xF2: 2,
    0x1A: 2, 0x3A: 2, 0x5A: 2, 0x7A: 2, 0xDA: 2, 0xFA: 2,
    0x04: 3, 0x44: 3, 0x64: 3,
    0x14: 4, 0x34: 4, 0x54: 4, 0x74: 4, 0xD4: 4, 0xF4: 4,
    0x0C: 4,
    0x1C: 4, 0x3C: 4, 0x5C: 4, 0x7C: 4, 0xDC: 4, 0xFC: 4,
    0x80: 2, 0x82: 2, 0x89: 2, 0xC2: 2, 0xE2: 2,
}

def get_cycles(opcode: int, mode: str) -> Tuple[int, bool, bool]:
    """
    Get cycle count information for an opcode.
    
    Args:
        opcode: The 6502 opcode byte (0x00-0xFF)
        mode: Addressing mode string (e.g., 'absolute_x', 'immediate')
        
    Returns:
        Tuple of (base_cycles, has_page_penalty, is_branch):
        - base_cycles: Minimum cycles this instruction takes
        - has_page_penalty: True if +1 cycle when crossing page boundary
        - is_branch: True if this is a branch instruction (+1 if taken, +2 if page crossed)
        
    Examples:
        >>> get_cycles(0xA9, 'immediate')  # LDA #$00
        (2, False, False)
        >>> get_cycles(0xBD, 'absolute_x')  # LDA $1000,X
        (4, True, False)
        >>> get_cycles(0xD0, 'relative')  # BNE
        (2, False, True)
    """
    base_cycles = CYCLE_COUNTS.get(opcode, 2)  # Default to 2 if unknown
    
    # Instructions that can take +1 cycle on page boundary crossing
    page_penalty_modes = ['absolute_x', 'absolute_y', 'indirect_y']
    page_penalty_opcodes = [
        # LDA, LDX, LDY, EOR, AND, ORA, ADC, SBC, CMP
        0xBD, 0xB9, 0xB1,  # LDA
        0xBE,              # LDX
        0xBC,              # LDY
        0x5D, 0x59, 0x51,  # EOR
        0x3D, 0x39, 0x31,  # AND
        0x1D, 0x19, 0x11,  # ORA
        0x7D, 0x79, 0x71,  # ADC
        0xFD, 0xF9, 0xF1,  # SBC
        0xDD, 0xD9, 0xD1,  # CMP
    ]
    
    has_page_penalty = (mode in page_penalty_modes and opcode in page_penalty_opcodes)
    
    # Branch instructions take +1 if branch taken, +2 if page boundary crossed
    branch_opcodes = [0x90, 0xB0, 0xF0, 0x30, 0xD0, 0x10, 0x50, 0x70]
    is_branch = opcode in branch_opcodes
    
    return base_cycles, has_page_penalty, is_branch

def format_cycles(opcode: int, mode: str) -> str:
    """
    Format cycle count information as a human-readable string.
    
    Args:
        opcode: The 6502 opcode byte
        mode: Addressing mode string
        
    Returns:
        Formatted cycle count string:
        - "2" for fixed 2-cycle instruction
        - "4+p" for instruction with page boundary penalty
        - "2+t+p" for branch (+ if taken, + if page crossed)
        
    Examples:
        >>> format_cycles(0xA9, 'immediate')
        '2'
        >>> format_cycles(0xBD, 'absolute_x')
        '4+p'
        >>> format_cycles(0xD0, 'relative')
        '2+t+p'
    """
    base, page_penalty, is_branch = get_cycles(opcode, mode)
    
    if is_branch:
        return f"{base}+t+p"  # +t if taken, +p if page crossed
    elif page_penalty:
        return f"{base}+p"    # +p if page crossed
    else:
        return str(base)

def get_instruction_comment(mnemonic: str, operand_str: str, addr: int) -> str:
    """
    Generate an intelligent, context-aware comment for an instruction.
    
    Args:
        mnemonic: Instruction mnemonic (e.g., 'LDA', 'STA', 'BNE')
        operand_str: Formatted operand string (e.g., '#$00', 'WSYNC', '$F000')
        addr: Memory address of the instruction
        
    Returns:
        Comment string (including leading '; ') or empty string if no comment needed
        
    Examples:
        >>> get_instruction_comment('STA', 'WSYNC', 0xF000)
        '; Wait for horizontal blank'
        >>> get_instruction_comment('LDA', '#$00', 0xF001)
        '; Clear accumulator'
    """
    
    # Graphics-related comments
    if operand_str in ['GRP0', 'GRP1']:
        return f"; Update player {operand_str[-1]} graphics"
    elif operand_str == 'ENABL':
        return "; Enable/disable ball sprite"
    elif operand_str in ['ENAM0', 'ENAM1']:
        return f"; Enable/disable missile {operand_str[-1]}"
    elif operand_str in ['PF0', 'PF1', 'PF2']:
        return f"; Set playfield register {operand_str[-1]}"
    elif operand_str == 'COLUPF':
        return "; Set playfield color"
    elif operand_str == 'COLUBK':
        return "; Set background color"
    elif operand_str in ['COLUP0', 'COLUP1']:
        return f"; Set player {operand_str[-1]} color"
    elif operand_str == 'CTRLPF':
        return "; Control playfield (reflect/score/priority)"
    elif operand_str in ['REFP0', 'REFP1']:
        return f"; Reflect player {operand_str[-1]} horizontally"
    
    # Position/motion comments
    elif operand_str in ['RESP0', 'RESP1']:
        return f"; Reset player {operand_str[-1]} position"
    elif operand_str in ['RESM0', 'RESM1']:
        return f"; Reset missile {operand_str[-1]} position"
    elif operand_str == 'RESBL':
        return "; Reset ball position"
    elif operand_str in ['HMP0', 'HMP1']:
        return f"; Set horizontal motion for player {operand_str[-1]}"
    elif operand_str == 'HMOVE':
        return "; Apply horizontal motion"
    elif operand_str == 'HMCLR':
        return "; Clear horizontal motion registers"
    
    # Sync/timing comments
    elif operand_str == 'WSYNC':
        return "; Wait for horizontal blank"
    elif operand_str == 'VSYNC':
        return "; Vertical sync signal"
    elif operand_str == 'VBLANK':
        return "; Vertical blank control"
    
    # Audio comments
    elif operand_str in ['AUDC0', 'AUDC1']:
        return f"; Audio control channel {operand_str[-1]}"
    elif operand_str in ['AUDF0', 'AUDF1']:
        return f"; Audio frequency channel {operand_str[-1]}"
    elif operand_str in ['AUDV0', 'AUDV1']:
        return f"; Audio volume channel {operand_str[-1]}"
    
    # Input/collision comments
    elif operand_str == 'SWCHA':
        return "; Read joystick inputs"
    elif operand_str == 'SWCHB':
        return "; Read console switches (RESET/SELECT)"
    elif operand_str == 'CXCLR':
        return "; Clear collision detection latches"
    elif operand_str.startswith('CX'):
        return "; Collision detection"
    
    # Timer comments
    elif operand_str == 'INTIM':
        return "; Read timer value"
    elif operand_str == 'TIM64T':
        return "; Set timer (64 clock interval)"
    elif operand_str in ['TIM1T', 'TIM8T', 'T1024T']:
        return f"; Set timer ({operand_str[3:-1]} clock interval)"
    
    # Size/number comments
    elif operand_str in ['NUSIZ0', 'NUSIZ1']:
        return f"; Number/size of player/missile {operand_str[-1]}"
    
    # Control flow comments
    elif mnemonic == 'JSR':
        return "; Call subroutine"
    elif mnemonic == 'RTS':
        return "; Return from subroutine"
    elif mnemonic == 'JMP':
        return "; Jump"
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
        return f"; {branch_names.get(mnemonic, 'Branch')}"
    
    # Stack operations
    elif mnemonic in ['PHA', 'PHP']:
        return "; Push to stack"
    elif mnemonic in ['PLA', 'PLP']:
        return "; Pull from stack"
    
    # Common patterns
    elif mnemonic == 'LDA' and operand_str.startswith('#$00'):
        return "; Clear accumulator"
    elif mnemonic == 'LDX' and operand_str.startswith('#$00'):
        return "; Clear X register"
    elif mnemonic == 'LDY' and operand_str.startswith('#$00'):
        return "; Clear Y register"
    elif mnemonic == 'CLC':
        return "; Clear carry flag"
    elif mnemonic == 'SEC':
        return "; Set carry flag"
    elif mnemonic == 'CLD':
        return "; Clear decimal mode"
    elif mnemonic == 'SED':
        return "; Set decimal mode"
    elif mnemonic == 'SEI':
        return "; Disable interrupts"
    elif mnemonic == 'CLI':
        return "; Enable interrupts"
    elif mnemonic == 'DEX':
        return "; Decrement X"
    elif mnemonic == 'DEY':
        return "; Decrement Y"
    elif mnemonic == 'INX':
        return "; Increment X"
    elif mnemonic == 'INY':
        return "; Increment Y"
    elif mnemonic == 'TAX':
        return "; Transfer A to X"
    elif mnemonic == 'TAY':
        return "; Transfer A to Y"
    elif mnemonic == 'TXA':
        return "; Transfer X to A"
    elif mnemonic == 'TYA':
        return "; Transfer Y to A"
    elif mnemonic == 'TSX':
        return "; Transfer stack pointer to X"
    elif mnemonic == 'TXS':
        return "; Transfer X to stack pointer"
    
    # Basic load/store operations
    elif mnemonic == 'LDA':
        return "; Load accumulator"
    elif mnemonic == 'LDX':
        return "; Load X register"
    elif mnemonic == 'LDY':
        return "; Load Y register"
    elif mnemonic == 'STA':
        return "; Store accumulator"
    elif mnemonic == 'STX':
        return "; Store X register"
    elif mnemonic == 'STY':
        return "; Store Y register"
    
    # Arithmetic operations
    elif mnemonic == 'ADC':
        return "; Add with carry"
    elif mnemonic == 'SBC':
        return "; Subtract with carry"
    elif mnemonic == 'INC':
        return "; Increment memory"
    elif mnemonic == 'DEC':
        return "; Decrement memory"
    
    # Logical operations
    elif mnemonic == 'AND':
        return "; Logical AND"
    elif mnemonic == 'ORA':
        return "; Logical OR"
    elif mnemonic == 'EOR':
        return "; Exclusive OR"
    elif mnemonic == 'BIT':
        return "; Bit test"
    
    # Shift/rotate operations
    elif mnemonic == 'ASL':
        return "; Arithmetic shift left"
    elif mnemonic == 'LSR':
        return "; Logical shift right"
    elif mnemonic == 'ROL':
        return "; Rotate left"
    elif mnemonic == 'ROR':
        return "; Rotate right"
    
    # Compare operations
    elif mnemonic == 'CMP':
        return "; Compare accumulator"
    elif mnemonic == 'CPX':
        return "; Compare X register"
    elif mnemonic == 'CPY':
        return "; Compare Y register"
    
    # Special operations
    elif mnemonic == 'NOP':
        return "; No operation"
    elif mnemonic == 'BRK':
        return "; Break (software interrupt)"
    elif mnemonic == 'RTI':
        return "; Return from interrupt"
    
    return ""  # No comment for this instruction

def get_section_comment(addr: int, prev_addr: Optional[int] = None) -> str:
    """
    Generate section headers for major code regions.
    
    Args:
        addr: Current memory address
        prev_addr: Previous address (optional, for detecting transitions)
        
    Returns:
        Section header comment string or empty string
        
    Note:
        This function contains hardcoded addresses for specific ROMs.
        For generic use, this should be made configurable.
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
# CLI LOOKUP TOOL
# ============================================================================


import sys

def format_opcode_table(mnemonic):
    """Format a table of all opcodes for a given mnemonic."""
    # Find all opcodes for this mnemonic
    opcodes_for_mnemonic = []
    for opcode, (mn, size, mode) in OPCODES.items():
        if mn == mnemonic:
            cycles = CYCLE_COUNTS.get(opcode, '?')
            opcodes_for_mnemonic.append((opcode, mode, size, cycles))
    
    if not opcodes_for_mnemonic:
        return "No opcodes found for this mnemonic."
    
    # Sort by opcode value
    opcodes_for_mnemonic.sort()
    
    # Build table
    lines = []
    lines.append("  Opcode | Mode          | Bytes | Cycles")
    lines.append("  -------|---------------|-------|-------")
    
    for opcode, mode, size, cycles in opcodes_for_mnemonic:
        mode_str = mode.replace('_', ' ').title()
        lines.append(f"  ${opcode:02X}    | {mode_str:<13} | {size}     | {cycles}")
    
    return '\n'.join(lines)

def lookup_instruction(mnemonic):
    """Look up detailed information about an instruction."""
    mnemonic = mnemonic.upper()
    
    # Check if instruction exists
    found = False
    for opcode, (mn, size, mode) in OPCODES.items():
        if mn == mnemonic:
            found = True
            break
    
    if not found:
        print(f"Error: Unknown instruction '{mnemonic}'")
        print("\nUse --all to see all available instructions")
        return
    
    # Get instruction details
    info = INSTRUCTION_DETAILS.get(mnemonic, {})
    category = get_instruction_category(mnemonic)
    flags = OPCODE_FLAGS.get(mnemonic, '')
    operation = OPCODE_OPERATIONS.get(mnemonic, '')
    
    # Check if illegal
    is_illegal = mnemonic in INSTRUCTION_CATEGORIES.get('ILLEGAL', [])
    
    # Print formatted output
    print("=" * 70)
    print(f"  {mnemonic} - {info.get('name', mnemonic)}")
    if is_illegal:
        print("  *** ILLEGAL/UNDOCUMENTED OPCODE ***")
    print("=" * 70)
    print()
    
    print(f"Category:    {category}")
    print(f"Description: {info.get('description', 'No description available')}")
    print()
    
    if operation:
        print(f"Operation:   {operation}")
    
    if flags:
        flag_list = ' '.join(flags)
        print(f"Flags:       {flag_list}")
    else:
        print(f"Flags:       (none)")
    
    if info.get('notes'):
        print(f"Notes:       {info['notes']}")
    
    print()
    print("Addressing Modes:")
    print(format_opcode_table(mnemonic))
    print()

def list_all_instructions():
    """List all available instructions grouped by category."""
    print("=" * 70)
    print("  6502 Instruction Set")
    print("=" * 70)
    print()
    
    # Get unique mnemonics
    all_mnemonics = set()
    for opcode, (mn, size, mode) in OPCODES.items():
        all_mnemonics.add(mn)
    
    # Group by category
    for category_name, mnemonics in sorted(INSTRUCTION_CATEGORIES.items()):
        # Filter to only mnemonics that exist
        existing = [mn for mn in mnemonics if mn in all_mnemonics]
        if not existing:
            continue
        
        display_name = category_name.replace('_', ' ').title()
        print(f"{display_name}:")
        print(f"  {', '.join(sorted(existing))}")
        print()

def list_category(category_name):
    """List all instructions in a specific category."""
    category_name = category_name.upper()
    
    if category_name not in INSTRUCTION_CATEGORIES:
        print(f"Error: Unknown category '{category_name}'")
        print("\nAvailable categories:")
        for cat in sorted(INSTRUCTION_CATEGORIES.keys()):
            print(f"  {cat}")
        return
    
    mnemonics = INSTRUCTION_CATEGORIES[category_name]
    display_name = category_name.replace('_', ' ').title()
    
    print("=" * 70)
    print(f"  {display_name} Instructions")
    print("=" * 70)
    print()
    
    for mnemonic in sorted(mnemonics):
        info = INSTRUCTION_DETAILS.get(mnemonic, {})
        desc = info.get('description', 'No description')
        print(f"  {mnemonic:<6} - {desc}")
    print()

def main():
    if len(sys.argv) < 2:
        print("6502 Opcode Lookup Tool")
        print()
        print("Usage:")
        print("  python opcode_lookup.py <MNEMONIC>     Look up an instruction")
        print("  python opcode_lookup.py --all          List all instructions")
        print("  python opcode_lookup.py --category <CAT>  List category")
        print()
        print("Examples:")
        print("  python opcode_lookup.py LDA")
        print("  python opcode_lookup.py ADC")
        print("  python opcode_lookup.py --category ARITHMETIC")
        return
    
    arg = sys.argv[1]
    
    if arg == '--all':
        list_all_instructions()
    elif arg == '--category':
        if len(sys.argv) < 3:
            print("Error: --category requires a category name")
            print("\nAvailable categories:")
            for cat in sorted(INSTRUCTION_CATEGORIES.keys()):
                print(f"  {cat}")
        else:
            list_category(sys.argv[2])
    else:
        lookup_instruction(arg)

if __name__ == '__main__':
    main()
