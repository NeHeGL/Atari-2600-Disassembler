"""
Banking Module - Consolidated bank switching and address mapping

This module consolidates the following banking modules into a single file:
- bank_switcher.py: Bank switching logic for multi-bank ROMs
- bank_address_mapper.py: Address mapping between ROM and memory space

The Atari 2600 uses bank switching to access ROMs larger than 4KB.
This module handles the various bank switching schemes (F8, F6, F4, etc.)
and provides address translation utilities.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Set
from typing import Optional, Dict, List, Tuple, Set
from core_opcodes import OPCODES

# ============================================================================
# BANK SWITCHER
# ============================================================================


from typing import Optional, Dict, List, Tuple, Set

class BankSwitcher:
    """
    Detects and manages bank switching schemes for Atari 2600 ROMs.
    
    Supported schemes:
    - F8 (8K, 2 banks of 4K)
    - F6 (16K, 4 banks of 4K)
    - F4 (32K, 8 banks of 4K)
    - E0 (8K, 4 banks of 1K)
    - E7 (16K, complex)
    - 3F (512K, Tigervision)
    - FE (8K, Activision)
    """
    
    # Bank switching hotspot addresses
    BANK_SWITCH_SCHEMES = {
        'F8': {
            'size': 8192,
            'banks': 2,
            'bank_size': 4096,
            'hotspots': {0x1FF8: 0, 0x1FF9: 1},
            'description': 'F8 (8K, 2×4K banks)'
        },
        'F6': {
            'size': 16384,
            'banks': 4,
            'bank_size': 4096,
            'hotspots': {0x1FF6: 0, 0x1FF7: 1, 0x1FF8: 2, 0x1FF9: 3},
            'description': 'F6 (16K, 4×4K banks)'
        },
        'F4': {
            'size': 32768,
            'banks': 8,
            'bank_size': 4096,
            'hotspots': {
                0x1FF4: 0, 0x1FF5: 1, 0x1FF6: 2, 0x1FF7: 3,
                0x1FF8: 4, 0x1FF9: 5, 0x1FFA: 6, 0x1FFB: 7
            },
            'description': 'F4 (32K, 8×4K banks)'
        },
        'E0': {
            'size': 8192,
            'banks': 4,
            'bank_size': 1024,
            'hotspots': {
                0x1FE0: 0, 0x1FE1: 1, 0x1FE2: 2, 0x1FE3: 3,
                0x1FE4: 0, 0x1FE5: 1, 0x1FE6: 2, 0x1FE7: 3,
                0x1FE8: 0, 0x1FE9: 1, 0x1FEA: 2, 0x1FEB: 3
            },
            'description': 'E0 (8K, 4×1K banks, Parker Brothers)'
        },
        'FE': {
            'size': 8192,
            'banks': 2,
            'bank_size': 4096,
            'hotspots': {},  # FE uses different detection (monitors $01FE/$01FF)
            'description': 'FE (8K, 2×4K banks, Activision)'
        },
        'FA': {
            'size': 12288,
            'banks': 3,
            'bank_size': 4096,
            'hotspots': {0x1FF8: 0, 0x1FF9: 1, 0x1FFA: 2},
            'description': 'FA (12K, 3×4K banks, CBS)'
        },
        '3F': {
            'size': None,  # Variable size
            'banks': None,  # Depends on ROM size
            'bank_size': 2048,
            'hotspots': {},  # 3F uses writes to $3F
            'description': '3F (Tigervision, variable size)'
        }
    }
    
    def __init__(self) -> None:
        """Initialize the bank switcher with no detected scheme."""
        self.detected_scheme: Optional[str] = None
        self.bank_count: int = 0
        self.bank_size: int = 0
        self.hotspot_accesses: Dict[int, int] = {}  # Track which hotspots are accessed
        
    def detect_scheme(self, rom: bytearray, code_addresses: Set[int]) -> Optional[str]:
        """
        Detect which bank switching scheme (if any) is used.
        
        Args:
            rom: ROM data as bytearray
            code_addresses: Set of addresses identified as code
            
        Returns:
            Scheme name string (e.g., 'F8', 'F6') or None if no bank switching detected
            
        Note:
            Detection is based on ROM size and hotspot access patterns in the code.
        """
        rom_size = len(rom)
        
        # Check ROM size first
        if rom_size <= 4096:
            return None  # No bank switching needed for 4K or smaller
        
        # Try to detect scheme based on ROM size and hotspot accesses
        candidates = []
        
        # Check for exact size matches
        for scheme_name, scheme_info in self.BANK_SWITCH_SCHEMES.items():
            if scheme_info['size'] and rom_size == scheme_info['size']:
                candidates.append(scheme_name)
        
        # If no exact match, check for 3F (variable size)
        if not candidates and rom_size > 4096:
            candidates.append('3F')
        
        # Analyze code to find hotspot accesses
        hotspot_hits = self._find_hotspot_accesses(rom, code_addresses)
        
        # Score each candidate based on hotspot hits
        best_scheme = None
        best_score = 0
        
        for scheme_name in candidates:
            scheme_info = self.BANK_SWITCH_SCHEMES[scheme_name]
            score = 0
            
            # Count how many hotspots from this scheme are accessed
            for hotspot in scheme_info['hotspots'].keys():
                if hotspot in hotspot_hits:
                    score += hotspot_hits[hotspot]
            
            if score > best_score:
                best_score = score
                best_scheme = scheme_name
        
        # If we found hotspot accesses, use that scheme
        if best_score > 0:
            self.detected_scheme = best_scheme
            scheme_info = self.BANK_SWITCH_SCHEMES[best_scheme]
            self.bank_count = scheme_info['banks']
            self.bank_size = scheme_info['bank_size']
            self.hotspot_accesses = hotspot_hits
            return best_scheme
        
        # Otherwise, guess based on ROM size
        if rom_size == 8192:
            self.detected_scheme = 'F8'
            self.bank_count = 2
            self.bank_size = 4096
        elif rom_size == 16384:
            self.detected_scheme = 'F6'
            self.bank_count = 4
            self.bank_size = 4096
        elif rom_size == 32768:
            self.detected_scheme = 'F4'
            self.bank_count = 8
            self.bank_size = 4096
        else:
            # Unknown scheme
            self.detected_scheme = 'UNKNOWN'
            self.bank_count = rom_size // 4096
            self.bank_size = 4096
        
        return self.detected_scheme
    
    def _find_hotspot_accesses(self, rom: bytearray, code_addresses: Set[int]) -> Dict[int, int]:
        """
        Scan code for accesses to bank switching hotspots.
        
        Args:
            rom: ROM data as bytearray
            code_addresses: Set of addresses identified as code
            
        Returns:
            Dictionary mapping hotspot addresses to access counts
        """
        rom_size = len(rom)
        hotspot_hits = {}
        
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
            
            # Check for absolute addressing to hotspot range
            if mode == 'absolute' and size == 3:
                addr = rom[pc + 1] | (rom[pc + 2] << 8)
                
                # Check if this address is a known hotspot
                for scheme_info in self.BANK_SWITCH_SCHEMES.values():
                    if addr in scheme_info['hotspots']:
                        hotspot_hits[addr] = hotspot_hits.get(addr, 0) + 1
            
            # Check for indirect addressing that might hit hotspots
            elif mode in ['indirect_x', 'indirect_y'] and size == 2:
                # These could potentially hit hotspots, but harder to detect statically
                pass
            
            pc += size
        
        return hotspot_hits
    
    def get_bank_for_address(self, addr: int, base_addr: int = 0xF000) -> List[int]:
        """
        Determine which bank(s) an address could be in.
        
        Args:
            addr: Memory address to check
            base_addr: Base address of ROM in memory (default 0xF000 for 4K)
            
        Returns:
            List of possible bank numbers (without runtime info, returns all banks)
        """
        if not self.detected_scheme or self.detected_scheme == 'UNKNOWN':
            return [0]  # Default to bank 0
        
        # For most schemes, addresses $F000-$FFFF map to current bank
        # But we can't know which bank without runtime info
        # Return all possible banks
        return list(range(self.bank_count))
    
    def get_bank_info(self) -> Optional[Dict]:
        """
        Get information about detected bank switching.
        
        Returns:
            Dictionary with scheme details including:
            - scheme: Scheme name
            - description: Human-readable description
            - banks: Number of banks
            - bank_size: Size of each bank in bytes
            - hotspots: Hotspot address mappings
            - hotspot_accesses: Detected hotspot access counts
            Returns None if no scheme detected.
        """
        if not self.detected_scheme:
            return None
        
        scheme_info = self.BANK_SWITCH_SCHEMES.get(self.detected_scheme, {})
        
        return {
            'scheme': self.detected_scheme,
            'description': scheme_info.get('description', 'Unknown'),
            'banks': self.bank_count,
            'bank_size': self.bank_size,
            'hotspots': scheme_info.get('hotspots', {}),
            'hotspot_accesses': self.hotspot_accesses
        }
    
    def generate_bank_comment(self) -> str:
        """
        Generate a comment block describing the bank switching scheme.
        
        Returns:
            Formatted comment string for assembly output, or empty string if no scheme
        """
        if not self.detected_scheme:
            return ""
        
        info = self.get_bank_info()
        
        comment = "\n; ============================================================================\n"
        comment += f"; BANK SWITCHING DETECTED: {info['description']}\n"
        comment += "; ============================================================================\n"
        comment += f"; Banks: {info['banks']}\n"
        comment += f"; Bank Size: {info['bank_size']} bytes (${info['bank_size']:04X})\n"
        
        if info['hotspots']:
            comment += ";\n; Hotspot Addresses:\n"
            for hotspot, bank in sorted(info['hotspots'].items()):
                access_count = info['hotspot_accesses'].get(hotspot, 0)
                if access_count > 0:
                    comment += f";   ${hotspot:04X} -> Bank {bank} (accessed {access_count} times)\n"
                else:
                    comment += f";   ${hotspot:04X} -> Bank {bank}\n"
        
        comment += "; ============================================================================\n"
        
        return comment
    
    def is_hotspot_address(self, addr: int) -> Tuple[bool, Optional[int]]:
        """
        Check if an address is a bank switching hotspot.
        
        Args:
            addr: Memory address to check
            
        Returns:
            Tuple of (is_hotspot, bank_number):
            - is_hotspot: True if address is a hotspot
            - bank_number: Target bank number, or None if not a hotspot
        """
        if not self.detected_scheme:
            return (False, None)
        
        scheme_info = self.BANK_SWITCH_SCHEMES.get(self.detected_scheme, {})
        hotspots = scheme_info.get('hotspots', {})
        
        if addr in hotspots:
            return (True, hotspots[addr])
        
        return (False, None)


if __name__ == '__main__':
    print("Bank Switcher - Detects bank switching schemes in Atari 2600 ROMs")
    print("\nSupported schemes:")
    for name, info in BankSwitcher.BANK_SWITCH_SCHEMES.items():
        print(f"  {name}: {info['description']}")


# ============================================================================
# BANK ADDRESS MAPPER
# ============================================================================


from typing import Dict, Tuple, Optional, Set
from dataclasses import dataclass

@dataclass
class BankMapping:
    """Information about a specific bank."""
    bank_number: int
    rom_start: int  # Starting ROM offset
    rom_end: int    # Ending ROM offset (exclusive)
    mem_start: int  # Starting memory address
    mem_end: int    # Ending memory address (exclusive)
    
    def contains_offset(self, offset: int) -> bool:
        """Check if a ROM offset is in this bank."""
        return self.rom_start <= offset < self.rom_end
    
    def offset_to_address(self, offset: int) -> int:
        """Convert ROM offset to memory address for this bank."""
        if not self.contains_offset(offset):
            raise ValueError(f"Offset {offset} not in bank {self.bank_number}")
        return self.mem_start + (offset - self.rom_start)
    
    def address_to_offset(self, address: int) -> int:
        """Convert memory address to ROM offset for this bank."""
        if not (self.mem_start <= address < self.mem_end):
            raise ValueError(f"Address ${address:04X} not in bank {self.bank_number} range")
        return self.rom_start + (address - self.mem_start)


class BankAddressMapper:
    """
    Manages address translation for multi-bank ROMs.
    
    This class handles the complex task of translating between:
    1. ROM offsets (linear file position)
    2. Memory addresses (6507 address space)
    3. Bank numbers
    
    It maintains all code relationships (jumps, branches, calls) while
    remapping addresses for each bank.
    """
    
    def __init__(self, rom_size: int, bank_scheme: Optional[str], bank_count: int, bank_size: int):
        """
        Initialize the address mapper.
        
        Args:
            rom_size: Total size of ROM in bytes
            bank_scheme: Bank switching scheme (F8, F6, F4, etc.) or None for 4K
            bank_count: Number of banks
            bank_size: Size of each bank in bytes
        """
        self.rom_size = rom_size
        self.bank_scheme = bank_scheme
        self.bank_count = bank_count
        self.bank_size = bank_size
        self.banks: Dict[int, BankMapping] = {}
        
        # For non-banked ROMs
        if not bank_scheme or rom_size <= 4096:
            base_addr = 0x10000 - rom_size
            self.banks[0] = BankMapping(
                bank_number=0,
                rom_start=0,
                rom_end=rom_size,
                mem_start=base_addr,
                mem_end=0x10000
            )
            self.is_banked = False
        else:
            # For F8/F6/F4 schemes: each bank maps to $F000-$FFFF
            self.is_banked = True
            for bank_num in range(bank_count):
                rom_start = bank_num * bank_size
                rom_end = min(rom_start + bank_size, rom_size)
                
                # All banks map to the same memory range
                # (hardware switches which bank is visible)
                self.banks[bank_num] = BankMapping(
                    bank_number=bank_num,
                    rom_start=rom_start,
                    rom_end=rom_end,
                    mem_start=0xF000,  # Standard 4K bank address
                    mem_end=0x10000
                )
    
    def get_bank_for_offset(self, offset: int) -> int:
        """
        Get the bank number for a ROM offset.
        
        Args:
            offset: ROM offset (0 to rom_size-1)
            
        Returns:
            Bank number
        """
        for bank_num, bank in self.banks.items():
            if bank.contains_offset(offset):
                return bank_num
        raise ValueError(f"Offset {offset} not in any bank")
    
    def offset_to_address(self, offset: int) -> Tuple[int, int]:
        """
        Convert ROM offset to memory address and bank number.
        
        Args:
            offset: ROM offset
            
        Returns:
            Tuple of (memory_address, bank_number)
        """
        bank_num = self.get_bank_for_offset(offset)
        bank = self.banks[bank_num]
        address = bank.offset_to_address(offset)
        return (address, bank_num)
    
    def translate_labels(self, labels: Dict[int, str], rom_offsets: Dict[int, int]) -> Dict[int, Tuple[str, int]]:
        """
        Translate labels from ROM offsets to memory addresses with bank info.
        
        Args:
            labels: Dictionary mapping ROM offsets to label names
            rom_offsets: Dictionary mapping original addresses to ROM offsets
                        (used to reverse-lookup which offset a label refers to)
        
        Returns:
            Dictionary mapping memory addresses to (label_name, bank_number) tuples
        """
        translated = {}
        
        for offset, label_name in labels.items():
            address, bank_num = self.offset_to_address(offset)
            translated[address] = (label_name, bank_num)
        
        return translated
    
    def translate_operand_address(self, operand_addr: int, current_offset: int) -> Tuple[int, int, int]:
        """
        Translate an operand address, determining which bank it refers to.
        
        For banked ROMs, we need to figure out which bank an address refers to.
        This is tricky because the same address ($F000) could refer to different banks.
        
        Strategy:
        1. If the target is in the same bank as current instruction, use that bank
        2. Otherwise, we can't know for sure without runtime info, so mark it as ambiguous
        
        Args:
            operand_addr: The address in the operand (e.g., target of JSR)
            current_offset: ROM offset of the current instruction
            
        Returns:
            Tuple of (translated_address, target_bank, current_bank)
            - translated_address: The address to use in the output
            - target_bank: Which bank the target is in (or -1 if ambiguous)
            - current_bank: Which bank the current instruction is in
        """
        current_bank = self.get_bank_for_offset(current_offset)
        
        if not self.is_banked:
            # No banking, address is as-is
            return (operand_addr, 0, 0)
        
        # For banked ROMs, check if the address is in the banked region ($F000-$FFFF)
        if operand_addr < 0xF000:
            # Not in banked region (e.g., RAM, TIA, RIOT)
            return (operand_addr, -1, current_bank)
        
        # Address is in banked region - could be any bank
        # Check if it's in the current bank first (most common case)
        current_bank_mapping = self.banks[current_bank]
        
        # Calculate what ROM offset this address would be in the current bank
        try:
            target_offset = current_bank_mapping.address_to_offset(operand_addr)
            # Verify this offset is actually in the ROM
            if 0 <= target_offset < self.rom_size:
                # Target is in current bank
                return (operand_addr, current_bank, current_bank)
        except ValueError:
            pass
        
        # Not in current bank - check other banks
        # This is a cross-bank reference
        for bank_num, bank in self.banks.items():
            if bank_num == current_bank:
                continue
            try:
                target_offset = bank.address_to_offset(operand_addr)
                if 0 <= target_offset < self.rom_size:
                    # Found it in another bank
                    return (operand_addr, bank_num, current_bank)
            except ValueError:
                continue
        
        # Couldn't determine which bank - return as ambiguous
        return (operand_addr, -1, current_bank)
    
    def get_bank_info(self, bank_num: int) -> BankMapping:
        """Get information about a specific bank."""
        return self.banks[bank_num]
    
    def get_all_banks(self) -> Dict[int, BankMapping]:
        """Get all bank mappings."""
        return self.banks.copy()

