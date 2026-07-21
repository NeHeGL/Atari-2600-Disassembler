"""
Analyzer Module - Consolidated code and data analysis utilities

This module consolidates the following analyzer modules into a single file:
- code_analyzer.py: Code Analyzer functionality
- data_analyzer.py: Data Analyzer functionality
- pattern_recognizer.py: Pattern Recognizer functionality
- opcode_statistics.py: Opcode Statistics functionality
- dead_code_analyzer.py: Dead Code Analyzer functionality

These analyzers provide intelligent disassembly by detecting code patterns,
data sections, subroutines, and providing statistics about opcode usage.
"""

from typing import Dict, Optional, Set
from typing import Dict, Set
from typing import Dict, Set, List, Tuple
from typing import List, Tuple, Optional, Set, Dict
from typing import Tuple, List, Optional, Dict, Set

# ============================================================================
# CODE ANALYZER
# ============================================================================


from typing import List, Tuple, Optional, Set, Dict

def analyze_code_section(rom: bytearray, start_pc: int, end_pc: int, code_addresses: Set[int], base_addr: int) -> str:
    """
    Analyze a code section to guess its purpose.
    
    Args:
        rom: ROM data as bytearray
        start_pc: Start offset in ROM
        end_pc: End offset in ROM
        code_addresses: Set of addresses identified as code
        base_addr: Base address where ROM is loaded in memory
        
    Returns:
        Description string classifying the code section
    """
    if end_pc <= start_pc:
        return "Code Routine"
    
    size = end_pc - start_pc
    
    # Sample the code to look for patterns
    has_jsr = False
    has_rts = False
    has_graphics = False
    has_audio = False
    has_timer = False
    has_input = False
    has_collision = False
    has_loop = False
    
    pc = start_pc
    while pc < end_pc and pc < len(rom):
        if pc not in code_addresses:
            break
            
        opcode = rom[pc]
        
        # JSR = 20
        if opcode == 0x20:
            has_jsr = True
        # RTS = 60
        elif opcode == 0x60:
            has_rts = True
        # STA zeropage = 85
        elif opcode == 0x85 and pc + 1 < len(rom):
            addr = rom[pc + 1]
            # Graphics registers
            if addr in [0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x0D, 0x0E, 0x0F]:
                has_graphics = True
            # Audio registers
            elif addr in [0x15, 0x16, 0x17, 0x18, 0x19, 0x1A]:
                has_audio = True
            # Collision clear
            elif addr == 0x2C:
                has_collision = True
        # LDA absolute = AD
        elif opcode == 0xAD and pc + 2 < len(rom):
            addr = rom[pc + 1] | (rom[pc + 2] << 8)
            # Timer read
            if addr == 0x0284:
                has_timer = True
            # Joystick read
            elif addr == 0x0280:
                has_input = True
        # Branch instructions indicate loops
        elif opcode in [0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0]:
            has_loop = True
        
        # Move to next instruction (estimate)
        if opcode in [0x60, 0x40]:  # RTS, RTI
            pc += 1
        elif opcode in [0x20, 0x4C]:  # JSR, JMP
            pc += 3
        elif opcode in [0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0]:  # Branches
            pc += 2
        else:
            pc += 1
    
    # Determine description based on patterns
    if has_graphics and has_loop and size > 50:
        return "Display Kernel / Rendering Routine"
    elif has_graphics and not has_jsr:
        return "Graphics Update Routine"
    elif has_audio:
        return "Sound/Audio Routine"
    elif has_input:
        return "Input Handler / Joystick Reading"
    elif has_timer and has_loop:
        return "Timing / Wait Loop"
    elif has_collision:
        return "Collision Detection Routine"
    elif has_jsr and has_rts and size > 30:
        return "Subroutine"
    elif has_loop and size < 20:
        return "Small Loop / Helper Routine"
    elif size < 10:
        return "Short Routine"
    else:
        return "Code Routine"

def find_callers(rom: bytearray, target_pc: int, code_addresses: Set[int], base_addr: int, code_section_map: Optional[Dict[int, str]] = None) -> List[Tuple[int, Optional[str]]]:
    """
    Find all JSR instructions that call this address.
    
    Args:
        rom: ROM data as bytearray
        target_pc: Target program counter offset
        code_addresses: Set of addresses identified as code
        base_addr: Base address where ROM is loaded in memory
        code_section_map: Optional mapping of addresses to section descriptions
        
    Returns:
        List of (caller_address, section_description) tuples
    """
    callers = []
    target_addr = base_addr + target_pc
    
    pc = 0
    while pc < len(rom):
        if pc in code_addresses:
            opcode = rom[pc]
            # JSR = 0x20
            if opcode == 0x20 and pc + 2 < len(rom):
                call_target = rom[pc + 1] | (rom[pc + 2] << 8)
                if call_target == target_addr:
                    caller_addr = base_addr + pc
                    
                    # Find which section this caller belongs to
                    section_desc = None
                    if code_section_map:
                        # Find the section that contains this caller
                        for section_addr in sorted(code_section_map.keys(), reverse=True):
                            if caller_addr >= section_addr:
                                section_desc = code_section_map[section_addr]
                                break
                    
                    callers.append((caller_addr, section_desc))
                pc += 3
            else:
                pc += 1
        else:
            pc += 1
    
    return callers

def check_jump_targets(rom: bytearray, target_pc: int, code_addresses: Set[int], base_addr: int) -> bool:
    """
    Check if this address is a JMP target (not JSR).
    
    Args:
        rom: ROM data as bytearray
        target_pc: Target program counter offset
        code_addresses: Set of addresses identified as code
        base_addr: Base address where ROM is loaded in memory
        
    Returns:
        True if address is a JMP target
    """
    target_addr = base_addr + target_pc
    
    pc = 0
    while pc < len(rom):
        if pc in code_addresses:
            opcode = rom[pc]
            # JMP absolute = 0x4C
            if opcode == 0x4C and pc + 2 < len(rom):
                jump_target = rom[pc + 1] | (rom[pc + 2] << 8)
                if jump_target == target_addr:
                    return True
                pc += 3
            else:
                pc += 1
        else:
            pc += 1
    
    return False

def check_indirect_calls(rom: bytearray, target_pc: int, code_addresses: Set[int], base_addr: int) -> bool:
    """
    Check if this might be called via indirect jump (JMP indirect).
    
    Args:
        rom: ROM data as bytearray
        target_pc: Target program counter offset
        code_addresses: Set of addresses identified as code
        base_addr: Base address where ROM is loaded in memory
        
    Returns:
        True if indirect jumps exist in the ROM
    """
    pc = 0
    while pc < len(rom):
        if pc in code_addresses:
            opcode = rom[pc]
            # JMP indirect = 0x6C
            if opcode == 0x6C:
                return True  # Indirect jumps exist, this could be a target
            pc += 1
        else:
            pc += 1
    
    return False

def get_code_section_comment(rom, start_pc, end_pc, code_addresses, base_addr, code_section_map=None, show_xrefs=True, xref=None, labels=None):
    """
    Generate a descriptive comment for a code section
    """
    description = analyze_code_section(rom, start_pc, end_pc, code_addresses, base_addr)
    
    # Calculate actual code size (only count bytes that are in code_addresses)
    size = sum(1 for pc in range(start_pc, end_pc) if pc in code_addresses)
    start_addr = base_addr + start_pc
    
    # Format as professional header
    header = "\n; ============================================================================\n"
    header += f"; {description.upper()}\n"
    header += f"; {size} bytes starting at ${start_addr:04X}\n"
    
    # Add caller information if show_xrefs is True
    if show_xrefs:
        # Use accurate xref data if available, otherwise fall back to heuristic
        if xref and start_addr in xref.called_by:
            # Use the accurate cross-reference data
            callers = xref.called_by[start_addr]
            caller_strs = []
            
            for caller_addr in sorted(callers):
                # Get the label name if it exists
                if labels and caller_addr in labels:
                    caller_name = labels[caller_addr]
                else:
                    caller_name = f"${caller_addr:04X}"
                
                # Find which section this caller belongs to
                section_desc = None
                if code_section_map:
                    for section_addr in sorted(code_section_map.keys(), reverse=True):
                        if caller_addr >= section_addr:
                            section_desc = code_section_map[section_addr]
                            break
                
                if section_desc:
                    caller_strs.append(f"{caller_name} ({section_desc})")
                else:
                    caller_strs.append(caller_name)
            
            # Show all callers
            if len(caller_strs) == 1:
                header += f"; Called from: {caller_strs[0]}\n"
            elif len(caller_strs) > 1:
                header += f"; Called from: {caller_strs[0]},\n"
                for i, caller_str in enumerate(caller_strs[1:], 1):
                    if i < len(caller_strs) - 1:
                        header += f";              {caller_str},\n"
                    else:
                        header += f";              {caller_str}\n"
        else:
            # Fall back to heuristic caller finding
            callers = find_callers(rom, start_pc, code_addresses, base_addr, code_section_map)
            
            if callers:
                caller_strs = []
                for addr, section in callers:
                    if section:
                        caller_strs.append(f"${addr:04X} ({section})")
                    else:
                        caller_strs.append(f"${addr:04X}")
                
                if len(caller_strs) == 1:
                    header += f"; Called from: {caller_strs[0]}\n"
                else:
                    header += f"; Called from: {caller_strs[0]},\n"
                    for i, caller_str in enumerate(caller_strs[1:], 1):
                        if i < len(caller_strs) - 1:
                            header += f";              {caller_str},\n"
                        else:
                            header += f";              {caller_str}\n"
            else:
                # No JSR callers found - check for other possibilities
                is_jump_target = check_jump_targets(rom, start_pc, code_addresses, base_addr)
                has_indirect = check_indirect_calls(rom, start_pc, code_addresses, base_addr)
                
                if is_jump_target:
                    header += f"; Reached via: JMP (unconditional jump)\n"
                elif has_indirect:
                    header += f"; Reached via: Indirect jump (computed address)\n"
                else:
                    header += f"; Reached via: Fall-through or unreachable code\n"
    
    header += "; ============================================================================"
    
    return header


# ============================================================================
# DATA ANALYZER
# ============================================================================


from typing import Tuple, List, Optional, Dict, Set

def byte_to_ascii_art(byte_val: int, style: str = 'block') -> str:
    """
    Convert a byte to 8-character ASCII art representation.
    
    Args:
        byte_val: The byte value to convert (0-255)
        style: 'block' for █/░, 'hash' for #/., 'double' for ██/  
        
    Returns:
        8-character string representing the byte visually
        
    Example:
        >>> byte_to_ascii_art(0xFF, 'block')
        '████████'
        >>> byte_to_ascii_art(0xAA, 'hash')
        '#.#.#.#.'
    """
    art = ""
    for bit in range(7, -1, -1):
        if byte_val & (1 << bit):
            if style == 'hash':
                art += "#"
            elif style == 'double':
                art += "██"
            else:  # block
                art += "█"
        else:
            if style == 'hash':
                art += "."
            elif style == 'double':
                art += "  "
            else:  # block
                art += "░"
    return art

def detect_sprite_frames(data):
    """
    Don't try to detect individual frames - just return the whole data block.
    Let the user interpret what they're seeing.
    This is more reliable than trying to guess frame boundaries.
    """
    frames = []
    
    if len(data) > 0:
        # Return entire data block as one "frame"
        frames.append((0, len(data)))
    
    return frames

def generate_sprite_visual(data, start_offset=0, height=8, style='double'):
    """
    Generate a visual representation of a sprite frame.
    Returns list of strings, one per line of the sprite.
    """
    lines = []
    for i in range(height):
        if start_offset + i < len(data):
            byte_val = data[start_offset + i]
            visual = byte_to_ascii_art(byte_val, style)
            lines.append(visual)
        else:
            # Padding if data is shorter than height
            if style == 'double':
                lines.append("  " * 8)
            else:
                lines.append("░" * 8)
    return lines

def generate_sprite_preview(data):
    """
    Generate inline byte-by-byte visualization for graphics data.
    Shows hex value and visual representation side-by-side.
    This is the most useful format - you can see which byte creates each line.
    """
    if len(data) == 0:
        return None
    
    preview_lines = []
    preview_lines.append("; ╔══════════════════════════════════════════════════════════════════════════╗")
    preview_lines.append("; ║ GRAPHICS DATA VISUALIZATION                                              ║")
    preview_lines.append("; ╚══════════════════════════════════════════════════════════════════════════╝")
    preview_lines.append(";")
    preview_lines.append("; Byte-by-byte view (Offset | Hex Value | Visual):")
    preview_lines.append(";")
    
    # Show each byte with its visual representation
    for i, byte_val in enumerate(data):
        visual = byte_to_ascii_art(byte_val, style='double')
        line = f";   ${i:04X}: ${byte_val:02X}  {visual}"
        preview_lines.append(line)
    
    return "\n".join(preview_lines)

def detect_playfield_data(data):
    """
    Detect if data represents playfield graphics (PF0/PF1/PF2).
    Playfield data is typically 3 bytes per scanline (PF0, PF1, PF2).
    Returns (is_playfield, details_string)
    """
    if len(data) < 3:
        return (False, "")
    
    # Check if size is multiple of 3 (PF0, PF1, PF2 triplets)
    if len(data) % 3 == 0:
        scanlines = len(data) // 3
        # Playfield data often has specific patterns
        # PF0 uses only 4 bits (upper nibble), PF1 and PF2 use all 8 bits
        pf0_pattern = all(data[i] & 0x0F == 0 for i in range(0, len(data), 3))
        
        if pf0_pattern and scanlines <= 192:  # Max 192 scanlines
            return (True, f"{scanlines} scanlines")
    
    return (False, "")

def calculate_sprite_symmetry(data):
    """
    Calculate vertical symmetry score for sprite data.
    Returns score 0-100 (100 = perfect symmetry)
    """
    if len(data) == 0:
        return 0
    
    matching_lines = 0
    for byte_val in data:
        # Check if byte is vertically symmetric (mirror across center)
        left_half = (byte_val >> 4) & 0x0F  # Upper 4 bits
        right_half = byte_val & 0x0F  # Lower 4 bits
        
        # Reverse the right half bits
        reversed_right = 0
        for i in range(4):
            if right_half & (1 << i):
                reversed_right |= (1 << (3 - i))
        
        if left_half == reversed_right:
            matching_lines += 1
    
    return int((matching_lines / len(data)) * 100)

def calculate_horizontal_symmetry(data):
    """
    Calculate horizontal symmetry score for sprite data.
    Checks if top half mirrors bottom half.
    Returns score 0-100 (100 = perfect horizontal symmetry)
    """
    if len(data) < 2:
        return 0
    
    # Only check if height is even
    if len(data) % 2 != 0:
        return 0
    
    mid = len(data) // 2
    top_half = data[:mid]
    bottom_half = data[mid:]
    
    # Reverse bottom half and compare
    bottom_reversed = list(reversed(bottom_half))
    
    matching_lines = sum(1 for i in range(mid) if top_half[i] == bottom_reversed[i])
    
    return int((matching_lines / mid) * 100)

def detect_animation_sequence(data):
    """
    Detect if sprite data contains animation frames.
    Returns (has_animation, frame_count, frame_height, similarity_score)
    """
    if len(data) < 16:
        return (False, 0, 0, 0)
    
    # Try common frame heights
    for frame_height in [8, 16, 32, 12, 24]:
        if len(data) % frame_height == 0:
            frame_count = len(data) // frame_height
            
            if frame_count < 2:
                continue
            
            # Extract frames
            frames = []
            for i in range(frame_count):
                frame_start = i * frame_height
                frame = data[frame_start:frame_start + frame_height]
                frames.append(frame)
            
            # Calculate similarity between consecutive frames
            # Animation frames should be similar but not identical
            similarities = []
            for i in range(len(frames) - 1):
                matching_bytes = sum(1 for j in range(frame_height) 
                                   if frames[i][j] == frames[i+1][j])
                similarity = (matching_bytes / frame_height) * 100
                similarities.append(similarity)
            
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0
            
            # Good animation: 30-80% similarity (similar but different)
            if 30 <= avg_similarity <= 80:
                return (True, frame_count, frame_height, int(avg_similarity))
    
    return (False, 0, 0, 0)

def estimate_sprite_dimensions(data):
    """
    Estimate sprite width and height based on data patterns.
    Returns (width, height, confidence)
    """
    if len(data) == 0:
        return (0, 0, 0)
    
    height = len(data)
    
    # Atari 2600 sprites are always 8 pixels wide (1 byte)
    # But we can detect if it's a double-width sprite (using both GRP0 and GRP1)
    
    # Check for patterns that suggest double-width
    # Look for alternating patterns or paired bytes
    if height >= 2:
        # Check if bytes come in pairs (suggesting 16-pixel wide sprite)
        paired = True
        for i in range(0, height - 1, 2):
            if i + 1 < height:
                # Check if consecutive bytes have similar density
                density1 = bin(data[i]).count('1')
                density2 = bin(data[i + 1]).count('1')
                if abs(density1 - density2) > 4:  # Very different densities
                    paired = False
                    break
        
        if paired and height % 2 == 0:
            return (16, height // 2, 70)  # 16 pixels wide, confidence 70%
    
    # Standard single-width sprite
    return (8, height, 90)  # 8 pixels wide, confidence 90%

def count_sprite_edges(data):
    """
    Count the number of edges (0->1 or 1->0 transitions) in sprite data.
    Real sprites typically have 2-8 major edges.
    """
    if len(data) == 0:
        return 0
    
    edge_count = 0
    prev_byte = 0
    
    for byte_val in data:
        # Count bit transitions within this byte
        for bit in range(7):
            curr_bit = (byte_val >> bit) & 1
            next_bit = (byte_val >> (bit + 1)) & 1
            if curr_bit != next_bit:
                edge_count += 1
        
        # Count transition from previous byte
        if prev_byte != 0 or byte_val != 0:  # Ignore all-zero transitions
            prev_last_bit = prev_byte & 1
            curr_first_bit = (byte_val >> 7) & 1
            if prev_last_bit != curr_first_bit:
                edge_count += 1
        
        prev_byte = byte_val
    
    # Normalize to edges per line
    return edge_count // max(1, len(data))

def calculate_sprite_density(data):
    """
    Calculate pixel density (ratio of 1s to total bits).
    Returns value 0.0-1.0
    """
    if len(data) == 0:
        return 0.0
    
    total_bits = len(data) * 8
    set_bits = 0
    
    for byte_val in data:
        set_bits += bin(byte_val).count('1')
    
    return set_bits / total_bits

def detect_sprite_quality(data):
    """
    Analyze sprite data quality using multiple heuristics.
    Returns (quality_score, details_dict)
    """
    if len(data) == 0:
        return (0, {})
    
    score = 0
    details = {}
    
    # Check for symmetry (0-30 points)
    symmetry = calculate_sprite_symmetry(data)
    details['symmetry'] = symmetry
    if symmetry > 50:
        score += int(symmetry * 0.3)  # Up to 30 points
    
    # Check for defined edges (0-25 points)
    edges_per_line = count_sprite_edges(data)
    details['edges_per_line'] = edges_per_line
    if 2 <= edges_per_line <= 8:
        score += 25
    elif 1 <= edges_per_line <= 10:
        score += 15
    
    # Check pixel density (0-20 points)
    density = calculate_sprite_density(data)
    details['density'] = density
    if 0.15 <= density <= 0.85:  # Not too sparse, not too dense
        score += 20
    elif 0.10 <= density <= 0.90:
        score += 10
    
    # Check for common sprite heights (0-15 points)
    height = len(data)
    details['height'] = height
    if height in [8, 16, 32]:
        score += 15
    elif height in [12, 24, 48]:
        score += 10
    elif height >= 4 and height <= 64:
        score += 5
    
    # Check for non-random patterns (0-10 points)
    # Real sprites rarely have all unique bytes
    unique_bytes = len(set(data))
    details['unique_bytes'] = unique_bytes
    if unique_bytes < len(data) * 0.8:  # Some repetition
        score += 10

    # STRONG PENALTY: Alternating-byte patterns are NOT sprite data.
    # When every odd-indexed byte (or every even-indexed byte) is the same value,
    # the data is an interleaved table (e.g. color+position pairs, timing tables).
    # Atari 2600 kernels commonly store interleaved data like:
    #   .byte value, $9B, value, $9B, ...  (position, TIA color, ...)
    # Real sprites have varied bytes at EVERY position.
    def _is_arith_prog(seq, min_len=3):
        """Return True if seq forms a non-trivial arithmetic progression (step != 0)."""
        if len(seq) < min_len:
            return False
        step = seq[1] - seq[0]
        if step == 0:
            return False  # constant sequence — handled by constant check above
        return all(seq[i] - seq[i-1] == step for i in range(2, len(seq)))

    if len(data) >= 4:
        even_bytes = data[0::2]
        odd_bytes  = data[1::2]
        # Check if all even-indexed bytes are identical
        if len(set(even_bytes)) == 1:
            score -= 60  # Disqualify: all even bytes same = interleaved data
            details['alternating_penalty'] = 'even'
        # Check if all odd-indexed bytes are identical
        elif len(set(odd_bytes)) == 1:
            score -= 60  # Disqualify: all odd bytes same = interleaved data
            details['alternating_penalty'] = 'odd'
        # Arithmetic-progression interleaved: the even or odd subsequence forms a
        # non-trivial arithmetic progression (e.g. river bank convergence tables
        # where every even byte increases +4 while every odd byte decreases -4).
        # These are lookup/geometry tables, NOT sprite graphics.
        elif _is_arith_prog(list(even_bytes)):
            score -= 50  # Strong penalty: arithmetic-progression interleaved data
            details['alternating_penalty'] = f'arith-prog-even (step={even_bytes[1]-even_bytes[0]})'
        elif _is_arith_prog(list(odd_bytes)):
            score -= 50  # Strong penalty: arithmetic-progression interleaved data
            details['alternating_penalty'] = f'arith-prog-odd (step={odd_bytes[1]-odd_bytes[0]})'
        # Softer penalty: >= 80% of even OR odd bytes are the same value
        else:
            even_mode = max(set(even_bytes), key=even_bytes.count)
            odd_mode  = max(set(odd_bytes),  key=odd_bytes.count)
            even_ratio = even_bytes.count(even_mode) / len(even_bytes)
            odd_ratio  = odd_bytes.count(odd_mode)  / len(odd_bytes)
            if even_ratio >= 0.80 or odd_ratio >= 0.80:
                score -= 40  # Strong penalty: mostly-alternating = likely table data
                details['alternating_penalty'] = f'soft ({max(even_ratio, odd_ratio):.0%})'

    details['total_score'] = score
    return (score, details)

def detect_sprite_frames(data):
    """
    Detect individual sprite frames within graphics data.
    Common heights: 8, 16, 32 bytes per frame.
    Uses quality scoring to validate sprite data.
    Returns list of (offset, height) tuples for each detected frame.
    """
    frames = []
    
    if len(data) == 0:
        return frames
    
    # Try common sprite heights
    for height in [8, 16, 32, 12, 24, 48]:
        if len(data) % height == 0:
            frame_count = len(data) // height
            
            # Validate frames using quality scoring
            valid = True
            total_quality = 0
            
            for i in range(frame_count):
                frame_start = i * height
                frame_data = data[frame_start:frame_start + height]
                
                # Check if frame has reasonable graphics content
                zero_count = frame_data.count(0)
                if zero_count == height:  # All zeros - probably not a sprite
                    valid = False
                    break
                
                # Check sprite quality
                quality_score, _ = detect_sprite_quality(frame_data)
                total_quality += quality_score
            
            # Average quality must be reasonable
            avg_quality = total_quality / frame_count if frame_count > 0 else 0
            
            if valid and avg_quality >= 40:  # Minimum 40% quality
                for i in range(frame_count):
                    frames.append((i * height, height))
                return frames
    
    # If no standard height works, check if whole block is sprite-like
    if not frames and len(data) > 0:
        quality_score, _ = detect_sprite_quality(data)
        if quality_score >= 35:  # Lower threshold for single sprites
            frames.append((0, len(data)))
    
    return frames

def detect_note_patterns(data):
    """
    Detect musical note patterns in sound data.
    Returns (has_patterns, pattern_type, score)
    """
    if len(data) < 4:
        return (False, None, 0)
    
    # Look for repeated sequences (common in music)
    # Check for 2, 3, or 4 byte patterns
    for pattern_len in [2, 3, 4]:
        if len(data) >= pattern_len * 2:
            pattern = data[:pattern_len]
            # Check if pattern repeats
            repeats = 0
            for i in range(0, len(data) - pattern_len + 1, pattern_len):
                if data[i:i+pattern_len] == pattern:
                    repeats += 1
            
            if repeats >= 2:
                return (True, f"{pattern_len}-byte pattern", 80)
    
    # Check for ascending/descending sequences (scales)
    if len(data) >= 4:
        ascending = sum(1 for i in range(len(data)-1) if data[i] < data[i+1])
        descending = sum(1 for i in range(len(data)-1) if data[i] > data[i+1])
        
        if ascending > len(data) * 0.6:
            return (True, "ascending scale", 70)
        elif descending > len(data) * 0.6:
            return (True, "descending scale", 70)
    
    return (False, None, 0)

def detect_rhythm_pattern(data):
    """
    Detect rhythmic patterns (timing/duration patterns).
    Returns (has_rhythm, rhythm_type, score)
    """
    if len(data) < 4:
        return (False, None, 0)
    
    # Check for alternating values (common rhythm pattern)
    if len(data) >= 4:
        alternating = True
        for i in range(len(data) - 2):
            if (data[i] == data[i+2]) and (data[i] != data[i+1]):
                continue
            else:
                alternating = False
                break
        
        if alternating:
            return (True, "alternating", 75)
    
    # Check for repeated durations
    unique_values = len(set(data))
    if 2 <= unique_values <= 4:  # Limited set of durations
        return (True, "rhythmic", 65)
    
    return (False, None, 0)

def detect_volume_envelope(data):
    """
    Detect volume envelope patterns (attack/decay/sustain/release).
    Returns (has_envelope, envelope_type, score)
    """
    if len(data) < 3:
        return (False, None, 0)
    
    # Volume data is typically 0-15
    if max(data) > 15:
        return (False, None, 0)
    
    # Check for fade-in (attack)
    if len(data) >= 3:
        increasing = all(data[i] <= data[i+1] for i in range(min(3, len(data)-1)))
        if increasing and data[0] < data[min(2, len(data)-1)]:
            return (True, "fade-in", 80)
    
    # Check for fade-out (release)
    if len(data) >= 3:
        decreasing = all(data[i] >= data[i+1] for i in range(min(3, len(data)-1)))
        if decreasing and data[0] > data[min(2, len(data)-1)]:
            return (True, "fade-out", 80)
    
    # Check for sustain (constant volume)
    unique_vals = len(set(data))
    if unique_vals == 1 and data[0] > 0:
        return (True, "sustain", 70)
    
    return (False, None, 0)

def detect_sound_quality(data):
    """
    Analyze sound data quality using multiple heuristics.
    Returns (quality_score, details_dict)
    """
    if len(data) < 4:
        return (0, {})
    
    score = 0
    details = {}
    
    max_val = max(data) if data else 0
    details['max_value'] = max_val
    
    # Check if values are in valid sound range (0-30 points)
    if max_val <= 15:  # Volume range
        score += 30
        details['data_type'] = 'volume'
    elif max_val <= 31:  # Frequency range
        score += 25
        details['data_type'] = 'frequency'
    else:
        # Not likely sound data
        return (0, details)
    
    # Check for note patterns (0-25 points)
    has_notes, note_type, note_score = detect_note_patterns(data)
    details['has_note_pattern'] = has_notes
    details['note_pattern_type'] = note_type
    if has_notes:
        score += int(note_score * 0.25)
    
    # Check for rhythm (0-20 points)
    has_rhythm, rhythm_type, rhythm_score = detect_rhythm_pattern(data)
    details['has_rhythm'] = has_rhythm
    details['rhythm_type'] = rhythm_type
    if has_rhythm:
        score += int(rhythm_score * 0.20)
    
    # Check for volume envelope (0-15 points)
    has_envelope, envelope_type, envelope_score = detect_volume_envelope(data)
    details['has_envelope'] = has_envelope
    details['envelope_type'] = envelope_type
    if has_envelope:
        score += int(envelope_score * 0.15)
    
    # Check for rests/silence (0-10 points)
    zero_count = data.count(0)
    zero_ratio = zero_count / len(data)
    details['silence_ratio'] = zero_ratio
    if 0.1 < zero_ratio < 0.5:  # Some silence but not too much
        score += 10
    
    details['total_score'] = score
    return (score, details)

def detect_sound_sequence(data):
    """
    Detect if data represents a sound/music sequence.
    Uses enhanced quality scoring with pattern analysis.
    Returns (is_sound, details_string)
    """
    if len(data) < 4:
        return (False, "")
    
    # Use quality scoring
    quality_score, quality_details = detect_sound_quality(data)
    
    # High quality sound (score >= 60)
    if quality_score >= 60:
        max_val = quality_details.get('max_value', 0)
        data_type = quality_details.get('data_type', 'unknown')
        details = []
        
        # Add pattern info
        if quality_details.get('has_note_pattern'):
            note_type = quality_details.get('note_pattern_type', 'unknown')
            details.append(note_type)
        
        # Add rhythm info
        if quality_details.get('has_rhythm'):
            rhythm_type = quality_details.get('rhythm_type', 'unknown')
            details.append(f"{rhythm_type} rhythm")
        
        # Add envelope info
        if quality_details.get('has_envelope'):
            envelope_type = quality_details.get('envelope_type', 'unknown')
            details.append(envelope_type)
        
        # Build description
        if details:
            detail_str = ", ".join(details)
            return (True, f"{len(data)} bytes, {data_type} data, {detail_str}")
        else:
            return (True, f"{len(data)} bytes, {data_type} data, max ${max_val:02X}")
    
    # Medium quality sound (score 40-59)
    elif quality_score >= 40:
        max_val = quality_details.get('max_value', 0)
        data_type = quality_details.get('data_type', 'unknown')
        return (True, f"{len(data)} bytes, {data_type} data")
    
    # Low quality - use old simple check
    else:
        max_val = max(data) if data else 0
        if max_val <= 31:
            zero_count = data.count(0)
            zero_ratio = zero_count / len(data)
            if 0.1 < zero_ratio < 0.7:
                return (True, f"{len(data)} bytes, max value ${max_val:02X}")
    
    return (False, "")

def detect_jump_table(data, base_addr, start_pc):
    """
    Detect if data represents a jump table (addresses).
    Jump tables are pairs of bytes forming 16-bit addresses.
    Returns (is_jump_table, entry_count, details)
    """
    if len(data) < 4 or len(data) % 2 != 0:
        return (False, 0, "")
    
    entry_count = len(data) // 2
    valid_entries = 0
    
    # Check if bytes form valid ROM addresses
    for i in range(0, len(data), 2):
        addr = data[i] | (data[i + 1] << 8)
        # Check if address is in valid ROM range
        if base_addr <= addr < base_addr + 0x1000:  # Typical 4K ROM
            valid_entries += 1
    
    # If most entries are valid addresses, it's likely a jump table
    if valid_entries >= entry_count * 0.7:  # 70% valid
        return (True, entry_count, f"{entry_count} entries")
    
    return (False, 0, "")

def analyze_color_gradient(data):
    """
    Detect if colors form a gradient (gradual hue or luminance change).
    Returns (has_gradient, gradient_type, score)
    """
    if len(data) < 3:
        return (False, None, 0)
    
    # Atari 2600 color format: CCCCLLLL (C=color/hue, L=luminance)
    # Upper nibble = hue (0-15), Lower nibble = luminance (0-15)
    
    hues = [(b >> 4) & 0x0F for b in data]
    luminances = [b & 0x0F for b in data]
    
    # Check for luminance gradient (brightness progression)
    lum_diffs = [abs(luminances[i+1] - luminances[i]) for i in range(len(luminances)-1)]
    avg_lum_diff = sum(lum_diffs) / len(lum_diffs) if lum_diffs else 0
    
    # Check for hue gradient (color progression)
    hue_diffs = [abs(hues[i+1] - hues[i]) for i in range(len(hues)-1)]
    avg_hue_diff = sum(hue_diffs) / len(hue_diffs) if hue_diffs else 0
    
    # Luminance gradient: small consistent changes in brightness
    if 0.5 <= avg_lum_diff <= 3.0 and all(d <= 4 for d in lum_diffs):
        # Check if mostly ascending or descending
        ascending = sum(1 for i in range(len(luminances)-1) if luminances[i+1] > luminances[i])
        descending = sum(1 for i in range(len(luminances)-1) if luminances[i+1] < luminances[i])
        if ascending > len(luminances) * 0.6 or descending > len(luminances) * 0.6:
            return (True, "luminance", 80)
    
    # Hue gradient: color wheel progression
    if 0.5 <= avg_hue_diff <= 2.5 and all(d <= 3 for d in hue_diffs):
        return (True, "hue", 70)
    
    # Mixed gradient: both hue and luminance change
    if avg_lum_diff > 0.3 and avg_hue_diff > 0.3:
        return (True, "mixed", 60)
    
    return (False, None, 0)

def analyze_color_families(data):
    """
    Group colors by hue family (reds, blues, greens, etc.).
    Returns (has_families, family_name, score)
    """
    if len(data) < 2:
        return (False, None, 0)
    
    # Atari 2600 hue values (upper nibble):
    # 0 = Gray, 1 = Gold, 2 = Orange, 3 = Red-Orange, 4 = Pink
    # 5 = Purple, 6 = Blue-Purple, 7 = Blue, 8 = Blue-Cyan
    # 9 = Cyan, A = Cyan-Green, B = Green, C = Yellow-Green
    # D = Orange-Green, E = Light Orange, F = Gray
    
    color_names = {
        0: "gray", 1: "gold", 2: "orange", 3: "red", 4: "pink",
        5: "purple", 6: "violet", 7: "blue", 8: "cyan-blue",
        9: "cyan", 10: "teal", 11: "green", 12: "yellow-green",
        13: "olive", 14: "tan", 15: "gray"
    }
    
    hues = [(b >> 4) & 0x0F for b in data]
    unique_hues = set(hues)
    
    # Check if all colors are in same family (within 2 hue values)
    if len(unique_hues) <= 3:
        min_hue = min(hues)
        max_hue = max(hues)
        if max_hue - min_hue <= 2:
            # Same color family
            primary_hue = max(set(hues), key=hues.count)
            family_name = color_names.get(primary_hue, "unknown")
            return (True, family_name, 85)
    
    # Check for complementary colors (opposite on color wheel)
    if len(unique_hues) == 2:
        hue_list = list(unique_hues)
        diff = abs(hue_list[0] - hue_list[1])
        if 6 <= diff <= 8:  # Roughly opposite
            return (True, "complementary", 75)
    
    return (False, None, 0)

def analyze_luminance_pattern(data):
    """
    Analyze luminance (brightness) patterns in color data.
    Returns (has_pattern, pattern_type, score)
    """
    if len(data) < 2:
        return (False, None, 0)
    
    luminances = [b & 0x0F for b in data]
    
    # Check for consistent luminance (same brightness)
    unique_lums = set(luminances)
    if len(unique_lums) == 1:
        return (True, "constant", 70)
    
    # Check for alternating pattern (bright/dark/bright/dark)
    if len(data) >= 4:
        alternating = True
        for i in range(len(luminances) - 2):
            if (luminances[i] < luminances[i+1]) == (luminances[i+1] < luminances[i+2]):
                alternating = False
                break
        if alternating:
            return (True, "alternating", 80)
    
    # Check for progressive darkening or brightening
    if len(data) >= 3:
        increasing = all(luminances[i] <= luminances[i+1] for i in range(len(luminances)-1))
        decreasing = all(luminances[i] >= luminances[i+1] for i in range(len(luminances)-1))
        
        if increasing:
            return (True, "brightening", 75)
        elif decreasing:
            return (True, "darkening", 75)
    
    return (False, None, 0)

def detect_color_palette_quality(data):
    """
    Analyze color palette quality using multiple heuristics.
    Returns (quality_score, details_dict)
    """
    if len(data) < 2 or len(data) > 32:
        return (0, {})
    
    score = 0
    details = {}
    
    # Check if values are valid Atari 2600 colors (mostly even)
    even_count = sum(1 for b in data if b % 2 == 0)
    even_ratio = even_count / len(data)
    details['even_ratio'] = even_ratio
    
    if even_ratio > 0.8:
        score += 25  # Very likely colors
    elif even_ratio > 0.6:
        score += 15  # Probably colors
    
    # Check for gradient patterns (0-30 points)
    has_gradient, gradient_type, gradient_score = analyze_color_gradient(data)
    details['has_gradient'] = has_gradient
    details['gradient_type'] = gradient_type
    if has_gradient:
        score += int(gradient_score * 0.3)  # Up to 30 points
    
    # Check for color families (0-25 points)
    has_families, family_name, family_score = analyze_color_families(data)
    details['has_families'] = has_families
    details['family_name'] = family_name
    if has_families:
        score += int(family_score * 0.25)  # Up to 25 points
    
    # Check for luminance patterns (0-20 points)
    has_lum_pattern, lum_pattern_type, lum_score = analyze_luminance_pattern(data)
    details['has_lum_pattern'] = has_lum_pattern
    details['lum_pattern_type'] = lum_pattern_type
    if has_lum_pattern:
        score += int(lum_score * 0.2)  # Up to 20 points
    
    # Check size (typical palettes: 2-16 colors)
    size = len(data)
    details['size'] = size
    if 2 <= size <= 8:
        score += 10  # Common palette size
    elif size <= 16:
        score += 5   # Reasonable palette size
    
    # Check for variety (at least 2 different colors)
    unique_colors = len(set(data))
    details['unique_colors'] = unique_colors
    if unique_colors >= 2:
        score += 10
    
    details['total_score'] = score
    return (score, details)

def detect_color_palette(data):
    """
    Detect if data represents a color palette.
    Uses enhanced quality scoring with gradient and family analysis.
    Returns (is_palette, details_string)
    """
    if len(data) < 2 or len(data) > 32:
        return (False, "")
    
    # Use quality scoring
    quality_score, quality_details = detect_color_palette_quality(data)
    
    # High quality palette (score >= 60)
    if quality_score >= 60:
        unique_colors = quality_details.get('unique_colors', 0)
        details = []
        
        # Add gradient info
        if quality_details.get('has_gradient'):
            gradient_type = quality_details.get('gradient_type', 'unknown')
            details.append(f"{gradient_type} gradient")
        
        # Add family info
        if quality_details.get('has_families'):
            family_name = quality_details.get('family_name', 'unknown')
            details.append(f"{family_name} family")
        
        # Add luminance pattern
        if quality_details.get('has_lum_pattern'):
            lum_type = quality_details.get('lum_pattern_type', 'unknown')
            details.append(f"{lum_type} brightness")
        
        # Build description
        if details:
            detail_str = ", ".join(details)
            return (True, f"{len(data)} colors, {unique_colors} unique, {detail_str}")
        else:
            return (True, f"{len(data)} colors, {unique_colors} unique")
    
    # Medium quality palette (score 40-59)
    elif quality_score >= 40:
        unique_colors = quality_details.get('unique_colors', 0)
        return (True, f"{len(data)} colors, {unique_colors} unique")
    
    # Low quality - use old simple check
    else:
        even_ratio = quality_details.get('even_ratio', 0)
        if even_ratio > 0.7:
            unique_colors = quality_details.get('unique_colors', 0)
            if unique_colors >= 2:
                return (True, f"{len(data)} colors, {unique_colors} unique")
    
    return (False, "")

def detect_register_address_table(rom: bytearray, start_pc: int, end_pc: int,
                                   code_addresses: Set[int], base_addr: int) -> bool:
    """
    Detect if a data block is a TIA register address table.

    Pattern: code loads data into X (LDX abs,Y or LDX abs,X) and then uses
    that X value to index into zero-page hardware registers (STA zp,X or
    STY zp,X / STX zp,X).  In this case the data bytes are *addresses*, not
    pixel values, and should NOT be classified as sprite graphics.

    Also detects the companion value table when a parallel LDA loads values
    that are then stored via `STA <VSYNC,X` style instructions.

    Returns True if the data is likely a register address / init table.
    """
    rom_size = len(rom)
    data_addr_lo = base_addr + start_pc
    data_addr_hi = base_addr + end_pc - 1

    # Only detect the pattern where data is loaded into X (LDX abs,Y or LDX abs,X)
    # and then used as an index into TIA registers (STA zp,X / STY zp,X).
    # We specifically look for LDX - not LDA - because:
    #   - LDX data,Y → STX/STA <reg,X  means bytes ARE register addresses
    #   - LDA data,Y → STA <reg        means bytes are register VALUES (not addresses)
    # Using LDA would catch audio/sprite value tables which are NOT register tables.
    for pc in range(rom_size - 2):
        if pc not in code_addresses:
            continue
        opcode = rom[pc]
        if opcode not in (0xBE, 0xB6):  # LDX abs,Y ($BE) or LDX zp,Y ($B6) ONLY
            continue
        if pc + 2 >= rom_size:
            continue
        ref_addr = rom[pc + 1] | (rom[pc + 2] << 8)
        # Does this load reference our data block?
        if not (data_addr_lo <= ref_addr <= data_addr_hi):
            continue

        # Found LDX from this block.  Now scan forward for STA/STX/STY zp,X
        # which would use X as a register index.
        fwd = pc + 3
        for _ in range(8):
            if fwd >= rom_size or fwd not in code_addresses:
                fwd += 1
                continue
            fwd_op = rom[fwd]
            # STA zp,X = $95, STY zp,X = $94, STX zp,Y = $96
            if fwd_op in (0x95, 0x94, 0x96):
                if fwd + 1 < rom_size:
                    zp = rom[fwd + 1]
                    if zp <= 0x2F:  # TIA register range ($00-$2F)
                        return True
            fwd_sz = 1
            if fwd_op in (0x20, 0x4C, 0x8D, 0x9D, 0x99, 0xBD, 0xB9, 0xAD):
                fwd_sz = 3
            elif fwd_op in (0x85, 0x95, 0x94, 0x96, 0xA9, 0xA2, 0xA0, 0xC9,
                             0xE0, 0xC0, 0x29, 0x09, 0x49, 0x69, 0xE9, 0x24):
                fwd_sz = 2
            fwd += fwd_sz

    return False


def analyze_data_region(rom: bytearray, start_pc: int, end_pc: int, code_addresses: Set[int], base_addr: int) -> str:
    """
    Analyze a data region to guess its purpose.
    
    Args:
        rom: ROM data as bytearray
        start_pc: Start offset in ROM
        end_pc: End offset in ROM
        code_addresses: Set of addresses identified as code
        base_addr: Base address where ROM is loaded in memory
        
    Returns:
        Description string with confidence level
        
    NOTE: All classifications are EDUCATED GUESSES based on heuristics.
    The analyzer looks for patterns typical of each data type, but cannot
    guarantee 100% accuracy. Use these labels as helpful hints, not absolute truth.
    """
    if end_pc <= start_pc:
        return "Data"
    
    data = rom[start_pc:end_pc]
    size = len(data)
    
    # Check for sprite/graphics data patterns
    # Graphics often have many zeros (blank lines) and specific bit patterns
    zero_count = data.count(0)
    zero_ratio = zero_count / size if size > 0 else 0
    
    # Check if data is referenced by indexed loads (common for sprite data)
    is_indexed_access = check_indexed_access(rom, start_pc, code_addresses, base_addr)
    
    # 1. Check for playfield graphics (HIGH confidence if pattern matches)
    is_playfield, pf_details = detect_playfield_data(data)
    if is_playfield:
        return f"Data (playfield graphics - {pf_details}) [High confidence]"
    
    # 2. Check for jump tables (HIGH confidence - validates addresses)
    is_jump_table, entry_count, jt_details = detect_jump_table(data, base_addr, start_pc)
    if is_jump_table:
        return f"Data (jump table - {jt_details}) [High confidence]"
    
    # 3. Check for sound sequences (MEDIUM confidence - pattern-based)
    is_sound, sound_details = detect_sound_sequence(data)
    if is_sound:
        return f"Data (sound sequence - {sound_details}) [Medium confidence]"
    
    # 4. Check for color palettes (MEDIUM confidence - format-based)
    is_palette, palette_details = detect_color_palette(data)
    if is_palette:
        return f"Data (color palette - {palette_details}) [Medium confidence]"

    # 4b. Check for TIA register address/init table (HIGH confidence).
    # This must run BEFORE the sprite heuristic because register address
    # tables (values 0x00-0x2F used as TIA register indices) score well on
    # the sprite density/edge metrics but are NOT graphics data.
    if detect_register_address_table(rom, start_pc, end_pc, code_addresses, base_addr):
        return f"Data (TIA register init table - {size} entries) [High confidence]"

    # 4c. Check for split lo/hi dispatch pointer table (HIGH confidence).
    # These are accessed via LDA abs,Y and contain either:
    #   - A run of repeated hi-bytes in the $E0-$FF range (hi-byte table)
    #   - Lo-bytes for ROM addresses ($F000-$FFFF range)
    # Must run BEFORE sprite heuristic because pointer table bytes often have
    # edge/density patterns that the sprite scorer misidentifies as graphics.
    # NOTE: check_indexed_access only looks 20 bytes back, so we also check
    # the byte-content heuristic independently for any data block that contains
    # a run of ROM hi-bytes (regardless of whether is_indexed_access fired).
    if size >= 4:
        # Count bytes that look like ROM hi-bytes, EXCLUDING $FF (which is ROM fill/padding)
        # and $E0 (uncommon as a real dispatch target page).
        # Real dispatch tables use specific ROM page values like $F9/$FA/$F8 etc.
        # $FF is overwhelmingly used as a sentinel value or ROM fill, not a pointer hi-byte.
        rom_hi_count = sum(1 for b in data if (b & 0xE0) == 0xE0 and b != 0xFF)
        # Count runs of 3+ identical non-$FF bytes (hi-byte tables have many repeats)
        max_run = 1
        cur_run = 1
        for i in range(1, len(data)):
            if data[i] == data[i-1] and data[i] != 0xFF:
                cur_run += 1
                max_run = max(max_run, cur_run)
            else:
                cur_run = 1
        hi_ratio = rom_hi_count / size
        # Strong signal: majority non-$FF ROM hi-bytes + a run of 3+ identical values
        # → almost certainly a hi-byte dispatch pointer table
        if hi_ratio >= 0.4 and max_run >= 3:
            return f"Data (dispatch pointer table - {size} entries) [High confidence]"
        # Weaker signal: some ROM hi-bytes + accessed via indexed load
        # Threshold is lower (0.20) because the indexed access itself is a strong signal
        if is_indexed_access and hi_ratio >= 0.20 and max_run >= 2:
            return f"Data (dispatch pointer table - {size} entries) [Medium confidence]"
        # Content-only: fraction of non-$FF ROM page bytes is strong enough signal
        # (accessor may be far away, outside the 20-byte check_indexed_access window)
        if hi_ratio >= 0.30 and max_run >= 2:
            return f"Data (dispatch pointer table - {size} entries) [Medium confidence]"

    # 4d-pre. Guard: check if these bytes form a valid 6502 instruction sequence.
    # If the data decodes cleanly as instructions (including illegal opcodes) and
    # ends with a control-flow terminator (RTS/RTI/JMP/BRK), it's almost certainly
    # code that the CPU simulator missed (e.g. due to the $FF stop or a cross-bank
    # jump). In that case skip all graphics heuristics — classifying code as
    # playfield or sprite data would be wrong and misleading.
    # We only apply this guard to small-to-medium blocks (≤ 64 bytes) where
    # misclassification is most likely; large blocks are unlikely to be one
    # coherent instruction stream.
    def _is_likely_code_sequence(data):
        """Return True if data decodes as a plausible 6502 instruction stream.
        
        A valid code sequence either:
        1. Terminates with RTS/RTI/JMP/BRK within the block, OR
        2. Decodes entirely without any invalid opcode bytes (fall-through code)
           AND contains at least 4 instructions (to avoid false positives on
           small data blocks that happen to contain valid opcode bytes).
        """
        if len(data) < 6 or len(data) > 64:
            return False
        pc = 0
        instr_count = 0
        bytes_consumed = 0
        while pc < len(data):
            b = data[pc]
            if b not in OPCODES:
                return False   # invalid opcode byte → not a clean code sequence
            mn, sz, md = OPCODES[b]
            # $00 (BRK) or $FF (ISC abs,X) at the very START is suspicious
            if pc == 0 and b in (0x00, 0xFF):
                return False
            if pc + sz > len(data):
                # Last instruction extends past our slice — that's fine for fall-through
                instr_count += 1
                bytes_consumed = len(data)
                break
            instr_count += 1
            bytes_consumed += sz
            # Explicit control-flow terminator within the block
            if mn in ('RTS', 'RTI', 'BRK') and instr_count >= 3:
                return True
            if mn == 'JMP' and instr_count >= 2:
                return True
            pc += sz
        # No explicit terminator — accept as fall-through code if:
        # - All bytes decoded cleanly (no invalid opcodes hit)
        # - We consumed ≥ 90 % of the block bytes (almost nothing left over)
        # - At least 4 instructions were decoded
        consumed_ratio = bytes_consumed / len(data)
        return instr_count >= 4 and consumed_ratio >= 0.85

    if size >= 6 and _is_likely_code_sequence(bytes(data)):
        return f"Data (untraced code - {size} bytes) [Medium confidence]"

    # 4d. Check for font / character set data.
    # Font data has a very small set of unique values (one entry per character),
    # no zeros (blank lines within a character would be $00 but fonts pack
    # non-zero pixels tightly), no bytes with the high bit set (player graphics
    # use the full byte but fonts for score/HUD typically stay in $01-$7F),
    # and a strong period repeat equal to the character height (typically 5 or 8).
    if size >= 10:
        unique_vals = len(set(data))
        zero_free   = (zero_count == 0)
        high_bit_count = sum(1 for b in data if b & 0x80)
        high_bit_ratio = high_bit_count / size

        if zero_free and high_bit_ratio < 0.05 and unique_vals <= max(16, size // 5):
            # Check for period repeat (character height candidates: 5, 6, 7, 8, 10)
            for period in (5, 6, 7, 8, 10):
                if size >= period * 3 and size % period == 0:
                    matches = sum(1 for i in range(size - period)
                                  if data[i] == data[i + period])
                    if matches / size >= 0.25:
                        char_count = size // period
                        return f"Data (font/character data - {char_count} chars, {period}px tall) [High confidence]"

    # 4e. Check for playfield graphics (high-bit dominant pattern).
    # Atari 2600 playfield registers PF1/PF2 are full 8-bit, but PF0 only uses
    # the upper nibble. Playfield data tends to have a high fraction of bytes
    # with the high bit set (background solid fills, borders, terrain shapes)
    # and moderate-to-high pixel density compared to sparse player sprites.
    if size >= 16:
        high_bit_count = sum(1 for b in data if b & 0x80)
        high_bit_ratio = high_bit_count / size
        density_all    = sum(bin(b).count('1') for b in data) / (size * 8)
        non_ff_count   = sum(1 for b in data if b != 0xFF)
        ff_ratio       = data.count(0xFF) / size

        # Strong playfield signal: >35% high-bit bytes, density > 0.30,
        # not dominated by $FF (which would be color/fill data instead)
        if high_bit_ratio >= 0.35 and density_all >= 0.30 and ff_ratio < 0.50:
            return f"Data (playfield graphics - density {density_all:.2f}, {int(high_bit_ratio*100)}% hi-bit) [High confidence]"
        # Medium signal: >25% high-bit + reasonably dense
        if high_bit_ratio >= 0.25 and density_all >= 0.25 and ff_ratio < 0.40:
            return f"Data (playfield graphics - density {density_all:.2f}) [Medium confidence]"

    # 5. Graphics data heuristics (ENHANCED with quality scoring)
    if size >= 8:
        # Use quality scoring to determine if this is sprite data
        quality_score, quality_details = detect_sprite_quality(data)
        
        # High quality sprite (score >= 60)
        if quality_score >= 60:
            symmetry = quality_details.get('symmetry', 0)
            density = quality_details.get('density', 0)
            edges = quality_details.get('edges_per_line', 0)

            # Build detail string from what we actually know
            details = []
            if symmetry > 70:
                details.append(f"{symmetry}% symmetric")
            elif symmetry > 50:
                details.append(f"{symmetry}% symmetric")
            if 0.2 <= density <= 0.8:
                details.append(f"density {density:.2f}")
            if 2 <= edges <= 8:
                details.append(f"{edges} edges/line")

            detail_str = ", ".join(details) if details else f"{size} bytes"
            return f"Data (sprite graphics - {detail_str}) [High confidence]"

        # Medium quality sprite (score 40-59)
        elif quality_score >= 40:
            return f"Data (sprite graphics - {size} bytes) [Medium confidence]"

        # Low quality but has some sprite characteristics (score 25-39)
        elif quality_score >= 25 and zero_ratio > 0.2:
            return f"Data (possibly sprite graphics - lower match score) [Low confidence]"
    
    # 6. Position/coordinate data (LOW-MEDIUM confidence - value range only)
    if size <= 16:
        max_val = max(data) if data else 0
        if max_val <= 160:  # Screen width is 160 pixels
            return "Data (likely positions - coordinates/offsets) [Low confidence]"
    
    # 7. Lookup tables (MEDIUM confidence - based on access pattern)
    if is_indexed_access and size >= 16:
        return "Data (lookup table) [Medium confidence]"
    
    # 8. Generic data (NO confidence - just size-based)
    if size < 8:
        return "Data (small table)"
    elif size < 32:
        return "Data (table)"
    else:
        return "Data (large table)"

def check_indexed_access(rom, data_pc, code_addresses, base_addr):
    """
    Check if any code in the ROM uses indexed addressing to access this data region.
    Scans the entire ROM (not just nearby bytes) because the accessor may be far away,
    e.g. a dispatch table at $FA47 accessed by code at $F941.
    """
    data_addr = base_addr + data_pc
    rom_size = len(rom)

    for pc in range(rom_size - 2):
        if pc not in code_addresses:
            continue
        opcode = rom[pc]
        # LDA abs,X = $BD, LDA abs,Y = $B9, STA abs,X = $9D, STA abs,Y = $99
        if opcode not in (0xBD, 0xB9, 0x9D, 0x99):
            continue
        addr = rom[pc + 1] | (rom[pc + 2] << 8)
        # Does this indexed load/store reference within 64 bytes of our data?
        if abs((addr - base_addr) - data_pc) < 64:
            return True

    return False

def check_audio_usage(rom, data_pc, code_addresses, base_addr):
    """
    Check if code nearby writes to audio registers
    """
    # Look at code before and after this data region
    search_start = max(0, data_pc - 30)
    search_end = min(len(rom), data_pc + 30)
    
    for pc in range(search_start, search_end):
        if pc in code_addresses and pc + 1 < len(rom):
            opcode = rom[pc]
            # Check for STA to audio registers
            # STA zp = 85, STA abs = 8D
            if opcode == 0x85:  # STA zeropage
                addr = rom[pc + 1]
                # Audio registers: AUDC0=15, AUDC1=16, AUDF0=17, AUDF1=18, AUDV0=19, AUDV1=1A
                if addr in [0x15, 0x16, 0x17, 0x18, 0x19, 0x1A]:
                    return True
    
    return False

def find_data_accessors(rom, data_start_pc, data_end_pc, code_addresses, base_addr, code_section_map=None):
    """
    Find all code that accesses this data region
    Returns list of (accessor_address, section_description) tuples
    """
    accessors = []
    accessors_set = set()  # Track unique accessors
    data_start_addr = base_addr + data_start_pc
    data_end_addr = base_addr + data_end_pc - 1
    
    pc = 0
    while pc < len(rom):
        if pc in code_addresses:
            opcode = rom[pc]
            
            # Check various addressing modes that access absolute addresses
            target_addr = None
            
            # Absolute addressing: LDA/STA/etc abs
            if opcode in [0xAD, 0xAE, 0xAC, 0x8D, 0x8E, 0x8C, 0x2C, 0x0D, 0x2D, 0x4D, 0x6D, 0xCD, 0xEC, 0xCC]:
                if pc + 2 < len(rom):
                    target_addr = rom[pc + 1] | (rom[pc + 2] << 8)
            # Absolute,X or Absolute,Y
            elif opcode in [0xBD, 0xB9, 0x9D, 0x99, 0x1D, 0x19, 0x3D, 0x39, 0x5D, 0x59, 0x7D, 0x79, 0xDD, 0xD9, 0xFD, 0xF9]:
                if pc + 2 < len(rom):
                    target_addr = rom[pc + 1] | (rom[pc + 2] << 8)
            # Indirect,Y addressing (common for graphics): LDA (zp),Y = B1, STA (zp),Y = 91
            elif opcode in [0xB1, 0x91]:
                # For indirect addressing, we can't know the exact target at disassembly time
                # But we can note that this code uses indirect addressing
                # Check if there are any immediate loads of high bytes near our data
                if pc + 10 < len(rom):
                    for check_pc in range(max(0, pc - 10), min(len(rom) - 2, pc + 10)):
                        if check_pc in code_addresses:
                            check_opcode = rom[check_pc]
                            # LDA #immediate = A9, LDY #immediate = A0, LDX #immediate = A2
                            if check_opcode in [0xA9, 0xA0, 0xA2] and check_pc + 1 < len(rom):
                                imm_val = rom[check_pc + 1]
                                # Check if this immediate value is the high byte of our data range
                                if imm_val == (data_start_addr >> 8) or imm_val == (data_end_addr >> 8):
                                    target_addr = data_start_addr  # Mark as accessing this region
                                    break
            
            # Check if target is in our data range
            if target_addr and data_start_addr <= target_addr <= data_end_addr:
                accessor_addr = base_addr + pc
                
                # Avoid duplicates
                if accessor_addr not in accessors_set:
                    accessors_set.add(accessor_addr)
                    
                    # Find which section this accessor belongs to
                    section_desc = None
                    if code_section_map:
                        for section_addr in sorted(code_section_map.keys(), reverse=True):
                            if accessor_addr >= section_addr:
                                section_desc = code_section_map[section_addr]
                                break
                    
                    accessors.append((accessor_addr, section_desc))
        
        pc += 1
    
    return accessors

def get_data_region_comment(rom, start_pc, end_pc, code_addresses, base_addr, code_section_map=None, show_xrefs=True, var_tracker=None, tia_data_map=None):
    """
    Generate a descriptive comment for a data region.
    Returns (header_comment, visualization_data) tuple.
    
    If tia_data_map is provided, we check whether any address in this data
    region appears as a key in the map. If so, we use the TIA register names
    to produce a much more informative header (e.g. "PLAYER GRAPHICS (GRP0/GRP1)"
    instead of the generic heuristic result).
    """
    size = end_pc - start_pc
    start_addr = base_addr + start_pc
    
    # --- TIA-context override: check if any byte in this region is in tia_data_map ---
    tia_override = None
    if tia_data_map:
        # Category register sets
        graphics_regs = {'GRP0', 'GRP1', 'PF0', 'PF1', 'PF2'}
        color_regs    = {'COLUP0', 'COLUP1', 'COLUPF', 'COLUBK'}
        audio_regs    = {'AUDC0', 'AUDC1', 'AUDF0', 'AUDF1', 'AUDV0', 'AUDV1'}
        position_regs = {'RESP0', 'RESP1', 'RESM0', 'RESM1', 'RESBL'}
        motion_regs   = {'HMP0', 'HMP1', 'HMM0', 'HMM1', 'HMBL'}

        # Count bytes (not just presence) per category using majority voting.
        # A single stray COLUPF access at the start of a 40-byte sprite block
        # should NOT cause the whole block to be labelled "Color Data".
        cat_counts = {'grp': 0, 'pf': 0, 'col': 0, 'aud': 0, 'pos': 0, 'mot': 0, 'other': 0}
        tia_regs_in_region = set()
        tia_hit_offsets = 0  # total bytes that have a TIA mapping

        for off in range(start_pc, end_pc):
            mem_addr = base_addr + off
            if mem_addr in tia_data_map:
                regs = set(tia_data_map[mem_addr])
                tia_regs_in_region.update(regs)
                tia_hit_offsets += 1
                # Categorise this byte by the most specific register it feeds
                if regs & {'GRP0', 'GRP1'}:
                    cat_counts['grp'] += 1
                elif regs & {'PF0', 'PF1', 'PF2'}:
                    cat_counts['pf'] += 1
                elif regs & color_regs:
                    cat_counts['col'] += 1
                elif regs & audio_regs:
                    cat_counts['aud'] += 1
                elif regs & position_regs:
                    cat_counts['pos'] += 1
                elif regs & motion_regs:
                    cat_counts['mot'] += 1
                else:
                    cat_counts['other'] += 1

        if tia_regs_in_region:
            # Only apply TIA override if the TIA-mapped bytes represent a meaningful
            # fraction of the block (≥ 10 %), OR the block is small (< 16 bytes).
            # Large blocks where only 1-2 bytes happen to feed a non-graphics TIA
            # register are better classified by the heuristic analyser.
            tia_fraction = tia_hit_offsets / size if size > 0 else 0
            dominant_cat = max(cat_counts, key=cat_counts.get)
            dominant_count = cat_counts[dominant_cat]

            # Always apply override for graphics categories (GRP/PF) even with few hits.
            # For non-graphics categories, require either:
            #   a) ≥ 20 % of the block maps to that category, OR
            #   b) the block is small (< 24 bytes)
            graphics_dominant = dominant_cat in ('grp', 'pf')
            non_graphics_sparse = (not graphics_dominant and
                                   tia_fraction < 0.20 and
                                   size >= 24)

            if non_graphics_sparse:
                # Too few non-graphics TIA hits to override — let heuristics decide
                pass
            else:
                has_grp  = tia_regs_in_region & {'GRP0', 'GRP1'}
                has_pf   = tia_regs_in_region & {'PF0', 'PF1', 'PF2'}
                has_col  = tia_regs_in_region & color_regs
                has_aud  = tia_regs_in_region & audio_regs
                has_pos  = tia_regs_in_region & position_regs
                has_mot  = tia_regs_in_region & motion_regs

                reg_str = ', '.join(sorted(tia_regs_in_region))

                # Use the dominant category to pick the label, not just "any" register.
                if dominant_cat == 'grp':
                    if has_pf:
                        tia_override = f"Player/Playfield Graphics Data ({reg_str})"
                    else:
                        grp_names = '/'.join(sorted(has_grp))
                        tia_override = f"Player Graphics Data ({grp_names})"
                elif dominant_cat == 'pf':
                    if has_grp:
                        tia_override = f"Player/Playfield Graphics Data ({reg_str})"
                    else:
                        pf_names = '/'.join(sorted(has_pf))
                        tia_override = f"Playfield Graphics Data ({pf_names})"
                elif dominant_cat == 'col' and has_col:
                    col_names = '/'.join(sorted(has_col))
                    tia_override = f"Color Data ({col_names})"
                elif dominant_cat == 'aud' and has_aud:
                    aud_names = '/'.join(sorted(has_aud))
                    tia_override = f"Audio Data ({aud_names})"
                elif dominant_cat == 'pos' and has_pos:
                    pos_names = '/'.join(sorted(has_pos))
                    tia_override = f"Position Data ({pos_names})"
                elif dominant_cat == 'mot' and has_mot:
                    mot_names = '/'.join(sorted(has_mot))
                    tia_override = f"Motion Data ({mot_names})"
                else:
                    tia_override = f"TIA Register Data ({reg_str})"
    
    # Use TIA override if available, otherwise use heuristic analysis
    if tia_override:
        description = tia_override
    else:
        description = analyze_data_region(rom, start_pc, end_pc, code_addresses, base_addr)
    
    # Find code that accesses this data
    accessors = find_data_accessors(rom, start_pc, end_pc, code_addresses, base_addr, code_section_map)
    
    # Format as professional header (use * for data sections, = for code sections)
    header = "\n; ****************************************************************************\n"
    header += f"; {description.upper()}\n"
    header += f"; {size} bytes starting at ${start_addr:04X}\n"
    
    # Decide whether this data section deserves pixel-by-pixel visualization.
    # Only visualize sprite/player/playfield graphics – NOT color palettes, sound
    # sequences, jump tables, etc.  The caller still controls whether visualization
    # is rendered at all (via the --visualize-data flag).
    data = rom[start_pc:end_pc]
    
    should_visualize = False
    desc_lower = description.lower()
    
    # TIA-sourced graphics data always visualizes
    if tia_override and any(k in tia_override.lower() for k in ['player graphics', 'playfield graphics', 'player/playfield']):
        should_visualize = True
    # Heuristic graphics data with reasonable confidence
    elif any(k in desc_lower for k in ['sprite graphics', 'playfield graphics', 'player graphics']):
        if any(k in desc_lower for k in ['high confidence', 'medium confidence', 'frames', 'symmetric', 'density', 'edges']):
            should_visualize = True
        elif size <= 256:  # Small unknown graphics blocks still get visualized
            should_visualize = True
    
    visualization = (start_pc, end_pc, data) if should_visualize else None
    
    # Add accessor information if found (only if show_xrefs is True)
    if accessors and show_xrefs:
        accessor_strs = []
        for addr, section in accessors:
            if section:
                accessor_strs.append(f"${addr:04X} ({section})")
            else:
                accessor_strs.append(f"${addr:04X}")
        
        # Show all accessors - always one per line for consistency
        if len(accessor_strs) == 1:
            # Single accessor - no comma
            header += f"; Accessed from: {accessor_strs[0]}\n"
        else:
            # Multiple accessors - one per line with commas
            header += f"; Accessed from: {accessor_strs[0]},\n"
            for i, accessor_str in enumerate(accessor_strs[1:], 1):
                if i < len(accessor_strs) - 1:
                    header += f";                {accessor_str},\n"
                else:
                    header += f";                {accessor_str}\n"
    elif show_xrefs:
        # No direct accessors found - likely accessed indirectly (only if show_xrefs is True)
        header += f"; Accessed via: Indirect addressing (pointers/computed addresses)\n"
    
    header += "; ****************************************************************************"
    
    return (header, visualization)


# ============================================================================
# PATTERN RECOGNIZER
# ============================================================================


from typing import Dict, Optional, Set
from core_opcodes import OPCODES

class PatternRecognizer:
    """
    Recognizes common Atari 2600 programming patterns in disassembled code.
    
    Provides intelligent pattern detection to generate meaningful comments
    and improve code readability.
    """
    
    def __init__(self) -> None:
        """Initialize the pattern recognizer."""
        self.patterns: list = []
        
    def analyze_patterns(self, rom: bytearray, code_addresses: Set[int], base_addr: int) -> Dict[int, Dict]:
        """
        Analyze code to find common patterns.
        
        Args:
            rom: ROM data as bytearray
            code_addresses: Set of addresses identified as code
            base_addr: Base address where ROM is loaded in memory
            
        Returns:
            Dictionary mapping PC addresses to pattern information dictionaries.
            Each pattern dict contains: type, size, description, and pattern-specific fields.
        """
        rom_size = len(rom)
        detected_patterns = {}
        
        pc = 0
        while pc < rom_size:
            if pc not in code_addresses:
                pc += 1
                continue
            
            # Check for delay loop pattern
            delay_info = self._check_delay_loop(rom, pc, code_addresses, rom_size)
            if delay_info:
                detected_patterns[pc] = delay_info
                pc += delay_info['size']
                continue
            
            # Check for memory clear pattern
            clear_info = self._check_memory_clear(rom, pc, code_addresses, rom_size)
            if clear_info:
                detected_patterns[pc] = clear_info
                pc += clear_info['size']
                continue
            
            # Check for sprite drawing kernel
            sprite_info = self._check_sprite_kernel(rom, pc, code_addresses, rom_size)
            if sprite_info:
                detected_patterns[pc] = sprite_info
                pc += sprite_info['size']
                continue
            
            # Check for scanline counting
            scanline_info = self._check_scanline_counter(rom, pc, code_addresses, rom_size)
            if scanline_info:
                detected_patterns[pc] = scanline_info
                pc += scanline_info['size']
                continue
            
            # Check for LFSR random number generator
            lfsr_info = self._check_lfsr(rom, pc, code_addresses, rom_size)
            if lfsr_info:
                detected_patterns[pc] = lfsr_info
                pc += lfsr_info['size']
                continue
            
            # Check for vertical blank routine
            vblank_info = self._check_vblank_routine(rom, pc, code_addresses, rom_size)
            if vblank_info:
                detected_patterns[pc] = vblank_info
                pc += vblank_info['size']
                continue
            
            # Check for horizontal positioning
            hpos_info = self._check_horizontal_positioning(rom, pc, code_addresses, rom_size)
            if hpos_info:
                detected_patterns[pc] = hpos_info
                pc += hpos_info['size']
                continue
            
            # Check for timer setup
            timer_info = self._check_timer_setup(rom, pc, code_addresses, rom_size)
            if timer_info:
                detected_patterns[pc] = timer_info
                pc += timer_info['size']
                continue
            
            pc += 1
        
        return detected_patterns
    
    def _check_delay_loop(self, rom, pc, code_addresses, rom_size):
        """
        Detect delay loop pattern:
        LDX #$nn / LDY #$nn
        DEX / DEY
        BNE loop
        """
        if pc + 4 >= rom_size:
            return None
        
        # Check for LDX #$nn or LDY #$nn
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 in ['LDX', 'LDY'] and mode1 == 'immediate':
            counter_value = rom[pc + 1]
            
            # Check for DEX/DEY
            if pc + size1 >= rom_size:
                return None
            
            opcode2 = rom[pc + size1]
            if opcode2 not in OPCODES:
                return None
            
            mnemonic2, size2, mode2 = OPCODES[opcode2]
            
            # Must match register (LDX->DEX, LDY->DEY)
            expected_dec = 'DEX' if mnemonic1 == 'LDX' else 'DEY'
            if mnemonic2 != expected_dec:
                return None
            
            # Check for BNE back to DEX/DEY
            if pc + size1 + size2 >= rom_size:
                return None
            
            opcode3 = rom[pc + size1 + size2]
            if opcode3 not in OPCODES:
                return None
            
            mnemonic3, size3, mode3 = OPCODES[opcode3]
            
            if mnemonic3 == 'BNE':
                # Calculate branch target
                offset = rom[pc + size1 + size2 + 1]
                if offset >= 128:
                    offset = offset - 256
                target_pc = pc + size1 + size2 + 2 + offset
                
                # Should branch back to DEX/DEY
                if target_pc == pc + size1:
                    # Calculate approximate cycles
                    # Loop: DEX (2) + BNE taken (3) = 5 cycles per iteration
                    # BNE not taken: 2 cycles
                    total_cycles = counter_value * 5 + 2
                    
                    return {
                        'type': 'delay_loop',
                        'size': size1 + size2 + size3,
                        'counter': counter_value,
                        'cycles': total_cycles,
                        'register': 'X' if mnemonic1 == 'LDX' else 'Y',
                        'description': f'DELAY LOOP - Wastes ~{total_cycles} cycles ({counter_value} iterations × 5 cycles)'
                    }
        
        return None
    
    def _check_memory_clear(self, rom, pc, code_addresses, rom_size):
        """
        Detect memory clear pattern:
        LDA #$00
        STA $xx,X / STA $xxxx,X
        INX / DEX
        BNE/CPX loop
        """
        if pc + 8 >= rom_size:
            return None
        
        # Check for LDA #$00
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 == 'LDA' and mode1 == 'immediate' and rom[pc + 1] == 0x00:
            # Check for STA with indexed addressing
            if pc + size1 >= rom_size:
                return None
            
            opcode2 = rom[pc + size1]
            if opcode2 not in OPCODES:
                return None
            
            mnemonic2, size2, mode2 = OPCODES[opcode2]
            
            if mnemonic2 == 'STA' and mode2 in ['zeropage_x', 'absolute_x']:
                # Check for INX or DEX
                if pc + size1 + size2 >= rom_size:
                    return None
                
                opcode3 = rom[pc + size1 + size2]
                if opcode3 not in OPCODES:
                    return None
                
                mnemonic3, size3, mode3 = OPCODES[opcode3]
                
                if mnemonic3 in ['INX', 'DEX']:
                    # Check for loop (BNE or CPX)
                    if pc + size1 + size2 + size3 >= rom_size:
                        return None
                    
                    opcode4 = rom[pc + size1 + size2 + size3]
                    if opcode4 not in OPCODES:
                        return None
                    
                    mnemonic4, size4, mode4 = OPCODES[opcode4]
                    
                    if mnemonic4 in ['BNE', 'CPX']:
                        return {
                            'type': 'memory_clear',
                            'size': size1 + size2 + size3 + size4,
                            'description': 'MEMORY CLEAR ROUTINE - Fills memory region with zeros'
                        }
        
        return None
    
    def _check_sprite_kernel(self, rom, pc, code_addresses, rom_size):
        """
        Detect sprite drawing kernel:
        WSYNC followed by GRP0/GRP1 writes
        """
        if pc + 6 >= rom_size:
            return None
        
        # Look for WSYNC
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 == 'STA' and mode1 in ['zeropage', 'absolute']:
            # Check if storing to WSYNC ($02 or $D002)
            addr = rom[pc + 1] if mode1 == 'zeropage' else (rom[pc + 1] | (rom[pc + 2] << 8))
            
            if addr == 0x02 or addr == 0xD002:  # WSYNC
                # Look for GRP0 or GRP1 write nearby (within 10 bytes)
                for offset in range(size1, min(size1 + 10, rom_size - pc)):
                    check_pc = pc + offset
                    if check_pc not in code_addresses:
                        break
                    
                    opcode = rom[check_pc]
                    if opcode not in OPCODES:
                        continue
                    
                    mnemonic, size, mode = OPCODES[opcode]
                    
                    if mnemonic == 'STA' and mode in ['zeropage', 'absolute']:
                        check_addr = rom[check_pc + 1] if mode == 'zeropage' else (rom[check_pc + 1] | (rom[check_pc + 2] << 8))
                        
                        if check_addr in [0x1B, 0xD01B, 0x1C, 0xD01C]:  # GRP0 or GRP1
                            return {
                                'type': 'sprite_kernel',
                                'size': offset + size,
                                'description': 'SPRITE DRAWING KERNEL - Updates player graphics each scanline'
                            }
        
        return None
    
    def _check_scanline_counter(self, rom, pc, code_addresses, rom_size):
        """
        Detect scanline counting loop:
        STA WSYNC
        DEX/DEY
        BNE loop
        """
        if pc + 6 >= rom_size:
            return None
        
        # Check for STA WSYNC
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 == 'STA' and mode1 in ['zeropage', 'absolute']:
            addr = rom[pc + 1] if mode1 == 'zeropage' else (rom[pc + 1] | (rom[pc + 2] << 8))
            
            if addr == 0x02 or addr == 0xD002:  # WSYNC
                # Check for DEX/DEY
                if pc + size1 >= rom_size:
                    return None
                
                opcode2 = rom[pc + size1]
                if opcode2 not in OPCODES:
                    return None
                
                mnemonic2, size2, mode2 = OPCODES[opcode2]
                
                if mnemonic2 in ['DEX', 'DEY']:
                    # Check for BNE back to WSYNC
                    if pc + size1 + size2 >= rom_size:
                        return None
                    
                    opcode3 = rom[pc + size1 + size2]
                    if opcode3 not in OPCODES:
                        return None
                    
                    mnemonic3, size3, mode3 = OPCODES[opcode3]
                    
                    if mnemonic3 == 'BNE':
                        offset = rom[pc + size1 + size2 + 1]
                        if offset >= 128:
                            offset = offset - 256
                        target_pc = pc + size1 + size2 + 2 + offset
                        
                        # Should branch back to STA WSYNC
                        if target_pc == pc:
                            return {
                                'type': 'scanline_counter',
                                'size': size1 + size2 + size3,
                                'description': 'SCANLINE COUNTER - Generates blank scanlines (76 cycles each)'
                            }
        
        return None
    
    def _check_lfsr(self, rom, pc, code_addresses, rom_size):
        """
        Detect Linear Feedback Shift Register (LFSR) random number generator:
        Common pattern: ASL/ROL with EOR for feedback
        """
        if pc + 8 >= rom_size:
            return None
        
        # Look for ASL A
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 == 'ASL' and mode1 == 'accumulator':
            # Look for BCC (skip feedback)
            if pc + size1 >= rom_size:
                return None
            
            opcode2 = rom[pc + size1]
            if opcode2 not in OPCODES:
                return None
            
            mnemonic2, size2, mode2 = OPCODES[opcode2]
            
            if mnemonic2 == 'BCC':
                # Look for EOR (feedback)
                if pc + size1 + size2 >= rom_size:
                    return None
                
                opcode3 = rom[pc + size1 + size2]
                if opcode3 not in OPCODES:
                    return None
                
                mnemonic3, size3, mode3 = OPCODES[opcode3]
                
                if mnemonic3 == 'EOR' and mode3 == 'immediate':
                    feedback = rom[pc + size1 + size2 + 1]
                    return {
                        'type': 'lfsr',
                        'size': size1 + size2 + size3,
                        'feedback': feedback,
                        'description': f'LFSR RANDOM NUMBER GENERATOR - Feedback: ${feedback:02X}'
                    }
        
        return None
    
    def _check_vblank_routine(self, rom, pc, code_addresses, rom_size):
        """
        Detect vertical blank routine:
        LDA #$02 / LDX #$02 / LDY #$02
        STA VBLANK
        """
        if pc + 6 >= rom_size:
            return None
        
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 in ['LDA', 'LDX', 'LDY'] and mode1 == 'immediate':
            value = rom[pc + 1]
            if value == 0x02:  # VBLANK enable value
                # Look for STA VBLANK
                if pc + size1 >= rom_size:
                    return None
                
                opcode2 = rom[pc + size1]
                if opcode2 not in OPCODES:
                    return None
                
                mnemonic2, size2, mode2 = OPCODES[opcode2]
                
                if mnemonic2 == 'STA' and mode2 == 'zeropage':
                    addr = rom[pc + size1 + 1]
                    if addr == 0x01:  # VBLANK
                        return {
                            'type': 'vblank_routine',
                            'size': size1 + size2,
                            'description': 'VERTICAL BLANK - Enables VBLANK (turns off display)'
                        }
        
        return None
    
    def _check_horizontal_positioning(self, rom, pc, code_addresses, rom_size):
        """
        Detect horizontal positioning routine:
        Fine positioning using RESP0/RESP1 with timing loops
        """
        if pc + 15 >= rom_size:
            return None
        
        # Look for RESP0 or RESP1 write
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 == 'STA' and mode1 == 'zeropage':
            addr = rom[pc + 1]
            if addr in [0x10, 0x11]:  # RESP0 or RESP1
                # Look for HMP0/HMP1 write nearby (fine positioning)
                for offset in range(size1, min(size1 + 12, rom_size - pc)):
                    check_pc = pc + offset
                    if check_pc not in code_addresses:
                        break
                    
                    opcode = rom[check_pc]
                    if opcode not in OPCODES:
                        continue
                    
                    mnemonic, size, mode = OPCODES[opcode]
                    
                    if mnemonic == 'STA' and mode == 'zeropage':
                        check_addr = rom[check_pc + 1]
                        if check_addr in [0x20, 0x21]:  # HMP0 or HMP1
                            return {
                                'type': 'horizontal_positioning',
                                'size': offset + size,
                                'description': 'HORIZONTAL POSITIONING - Sets sprite X position with fine adjustment'
                            }
        
        return None
    
    def _check_timer_setup(self, rom, pc, code_addresses, rom_size):
        """
        Detect timer setup:
        LDA #$nn
        STA TIM64T/TIM8T/TIM1T/T1024T
        """
        if pc + 6 >= rom_size:
            return None
        
        opcode1 = rom[pc]
        if opcode1 not in OPCODES:
            return None
        
        mnemonic1, size1, mode1 = OPCODES[opcode1]
        
        if mnemonic1 == 'LDA' and mode1 == 'immediate':
            timer_value = rom[pc + 1]
            
            if pc + size1 >= rom_size:
                return None
            
            opcode2 = rom[pc + size1]
            if opcode2 not in OPCODES:
                return None
            
            mnemonic2, size2, mode2 = OPCODES[opcode2]
            
            if mnemonic2 == 'STA' and mode2 in ['zeropage', 'absolute']:
                addr = rom[pc + size1 + 1] if mode2 == 'zeropage' else (rom[pc + size1 + 1] | (rom[pc + size1 + 2] << 8))
                
                timer_types = {
                    0x294: ('TIM1T', 1, 838),      # 838 nsec per interval
                    0x295: ('TIM8T', 8, 6700),     # 6.7 usec per interval
                    0x296: ('TIM64T', 64, 53600),  # 53.6 usec per interval
                    0x297: ('T1024T', 1024, 858200) # 858.2 usec per interval
                }
                
                if addr in timer_types:
                    name, clocks, nsec = timer_types[addr]
                    total_time = timer_value * nsec
                    if total_time >= 1000000:
                        time_str = f'{total_time / 1000000:.2f} ms'
                    else:
                        time_str = f'{total_time / 1000:.1f} µs'
                    
                    return {
                        'type': 'timer_setup',
                        'size': size1 + size2,
                        'timer': name,
                        'value': timer_value,
                        'description': f'TIMER SETUP - {name}: {timer_value} × {clocks} clocks = ~{time_str}'
                    }
        
        return None
    
    def get_pattern_comment(self, pc: int, patterns: Dict[int, Dict]) -> str:
        """
        Get comment for a detected pattern at given PC.
        
        Args:
            pc: Program counter address
            patterns: Dictionary of detected patterns
            
        Returns:
            Formatted comment string or empty string if no pattern at this PC
        """
        if pc in patterns:
            pattern = patterns[pc]
            return f"\n; ============================================================================\n; {pattern['description']}\n; ============================================================================\n"
        return ""


# ============================================================================
# OPCODE STATISTICS
# ============================================================================


from typing import Dict, Set
from core_opcodes import OPCODES

# Typical 6502 opcode frequency distribution (based on analysis of real ROMs)
# These percentages are approximate but represent common patterns in 6502 code
TYPICAL_OPCODE_DISTRIBUTION = {
    # Load/Store operations (very common)
    'LDA': 0.20,  # 20% of instructions
    'STA': 0.12,  # 12%
    'LDX': 0.05,
    'STX': 0.04,
    'LDY': 0.05,
    'STY': 0.04,
    
    # Branches (very common in control flow)
    'BNE': 0.08,
    'BEQ': 0.06,
    'BCC': 0.03,
    'BCS': 0.03,
    'BPL': 0.02,
    'BMI': 0.02,
    'BVC': 0.01,
    'BVS': 0.01,
    
    # Subroutines
    'JSR': 0.04,
    'RTS': 0.04,
    
    # Jumps
    'JMP': 0.02,
    
    # Arithmetic/Logic (common)
    'AND': 0.03,
    'ORA': 0.02,
    'EOR': 0.01,
    'ADC': 0.02,
    'SBC': 0.01,
    'CMP': 0.04,
    'CPX': 0.01,
    'CPY': 0.01,
    
    # Increments/Decrements
    'INC': 0.02,
    'DEC': 0.02,
    'INX': 0.02,
    'DEX': 0.02,
    'INY': 0.01,
    'DEY': 0.01,
    
    # Stack operations
    'PHA': 0.01,
    'PLA': 0.01,
    'PHP': 0.005,
    'PLP': 0.005,
    
    # Transfers
    'TAX': 0.01,
    'TXA': 0.01,
    'TAY': 0.01,
    'TYA': 0.01,
    'TSX': 0.005,
    'TXS': 0.005,
    
    # Shifts/Rotates
    'ASL': 0.01,
    'LSR': 0.01,
    'ROL': 0.01,
    'ROR': 0.01,
    
    # Flags (rare in typical code)
    'CLC': 0.01,
    'SEC': 0.01,
    'CLD': 0.002,
    'SED': 0.001,
    'CLI': 0.002,
    'SEI': 0.002,
    'CLV': 0.001,
    
    # Misc
    'BIT': 0.01,
    'NOP': 0.005,
    'RTI': 0.001,
    'BRK': 0.001,
}

def calculate_opcode_frequencies(rom: bytearray, code_addresses: Set[int]) -> Dict[str, float]:
    """
    Calculate the actual opcode frequency distribution in the ROM's code regions.
    
    Args:
        rom: ROM data as bytearray
        code_addresses: Set of offsets identified as code
        
    Returns:
        Dictionary mapping mnemonic to frequency (0.0-1.0)
    """
    opcode_counts = {}
    total_instructions = 0
    
    pc = 0
    while pc < len(rom):
        if pc not in code_addresses:
            pc += 1
            continue
        
        opcode = rom[pc]
        if opcode not in OPCODES:
            pc += 1
            continue
        
        mnemonic, size, mode = OPCODES[opcode]
        
        # Count this instruction
        opcode_counts[mnemonic] = opcode_counts.get(mnemonic, 0) + 1
        total_instructions += 1
        
        pc += size
    
    # Convert counts to frequencies
    frequencies = {}
    if total_instructions > 0:
        for mnemonic, count in opcode_counts.items():
            frequencies[mnemonic] = count / total_instructions
    
    return frequencies

def score_region_by_frequency(rom: bytearray, start: int, end: int) -> float:
    """
    Score a region based on how well its opcode distribution matches typical 6502 code.
    
    Uses chi-squared-like scoring: compares observed vs expected frequencies.
    Higher scores = more likely to be code.
    
    Args:
        rom: ROM data as bytearray
        start: Start offset of region
        end: End offset of region (exclusive)
        
    Returns:
        Score (0.0-1.0, higher = more likely code)
    """
    if end - start < 6:
        return 0.0  # Too small to analyze
    
    # Count opcodes in this region
    opcode_counts = {}
    total_instructions = 0
    pc = start
    
    while pc < end and pc < len(rom):
        opcode = rom[pc]
        
        if opcode not in OPCODES:
            # Invalid opcode - heavily penalize
            return 0.0
        
        mnemonic, size, mode = OPCODES[opcode]
        opcode_counts[mnemonic] = opcode_counts.get(mnemonic, 0) + 1
        total_instructions += 1
        
        pc += size
    
    if total_instructions == 0:
        return 0.0
    
    # Calculate frequencies
    observed_freq = {}
    for mnemonic, count in opcode_counts.items():
        observed_freq[mnemonic] = count / total_instructions
    
    # Calculate chi-squared-like score
    # Lower chi-squared = better match to expected distribution
    chi_squared = 0.0
    
    # Check all mnemonics we observed
    for mnemonic in observed_freq:
        observed = observed_freq[mnemonic]
        expected = TYPICAL_OPCODE_DISTRIBUTION.get(mnemonic, 0.01)  # Default to 1% if unknown
        
        # Chi-squared contribution: (observed - expected)^2 / expected
        chi_squared += ((observed - expected) ** 2) / expected
    
    # Also penalize if we're missing common opcodes
    common_opcodes = {'LDA', 'STA', 'BNE', 'BEQ', 'CMP', 'JSR', 'RTS'}
    missing_common = 0
    for mnemonic in common_opcodes:
        if mnemonic not in observed_freq:
            missing_common += 1
    
    # Convert chi-squared to a 0-1 score
    # Lower chi-squared = higher score
    # Typical good code has chi-squared around 0.1-0.5
    # Random data has chi-squared > 2.0
    base_score = 1.0 / (1.0 + chi_squared)
    
    # Apply penalty for missing common opcodes
    penalty = missing_common * 0.1
    final_score = max(0.0, base_score - penalty)
    
    return final_score

def validate_code_region(rom: bytearray, start: int, end: int, threshold: float = 0.3) -> bool:
    """
    Validate whether a region is likely to be code based on opcode frequency.
    
    Args:
        rom: ROM data as bytearray
        start: Start offset of region
        end: End offset of region (exclusive)
        threshold: Minimum score to consider as code (default 0.3)
        
    Returns:
        True if region appears to be code, False otherwise
    """
    score = score_region_by_frequency(rom, start, end)
    return score >= threshold

def analyze_frequency_distribution(rom: bytearray, code_addresses: Set[int]) -> Dict:
    """
    Analyze the frequency distribution of opcodes in the ROM and provide statistics.
    
    Args:
        rom: ROM data as bytearray
        code_addresses: Set of offsets identified as code
        
    Returns:
        Dictionary with analysis results
    """
    frequencies = calculate_opcode_frequencies(rom, code_addresses)
    
    # Find most/least common instructions
    sorted_freq = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)
    
    most_common = sorted_freq[:5] if len(sorted_freq) >= 5 else sorted_freq
    least_common = sorted_freq[-5:] if len(sorted_freq) >= 5 else []
    
    # Calculate chi-squared vs typical distribution
    chi_squared = 0.0
    for mnemonic, observed in frequencies.items():
        expected = TYPICAL_OPCODE_DISTRIBUTION.get(mnemonic, 0.01)
        chi_squared += ((observed - expected) ** 2) / expected
    
    return {
        'frequencies': frequencies,
        'most_common': most_common,
        'least_common': least_common,
        'chi_squared': chi_squared,
        'distribution_match': 'good' if chi_squared < 0.5 else 'fair' if chi_squared < 2.0 else 'poor'
    }


# ============================================================================
# DEAD CODE ANALYZER
# ============================================================================


from typing import Dict, Set, List, Tuple
from core_opcodes import OPCODES

def find_code_islands(rom: bytearray, code_addresses: Set[int], reachable_addresses: Set[int]) -> List[Tuple[int, int]]:
    """
    Find isolated "code islands" - regions marked as code but not reachable from main flow.
    
    Args:
        rom: ROM data as bytearray
        code_addresses: Set of all offsets identified as code
        reachable_addresses: Set of offsets reachable from entry points
        
    Returns:
        List of (start_offset, end_offset) tuples for each island
    """
    islands = []
    rom_size = len(rom)
    
    # Find unreachable code regions
    unreachable = code_addresses - reachable_addresses
    
    if not unreachable:
        return islands
    
    # Group consecutive unreachable bytes into islands
    sorted_unreachable = sorted(unreachable)
    island_start = sorted_unreachable[0]
    prev_offset = sorted_unreachable[0]
    
    for offset in sorted_unreachable[1:]:
        if offset != prev_offset + 1:
            # Gap found - end current island and start new one
            islands.append((island_start, prev_offset + 1))
            island_start = offset
        prev_offset = offset
    
    # Add final island
    islands.append((island_start, prev_offset + 1))
    
    return islands

def validate_subroutine(rom: bytearray, start: int, end: int) -> Dict:
    """
    Validate if a code island is a legitimate subroutine or just random data.
    
    Checks:
    - Does it end with RTS/RTI?
    - Does it have valid opcodes throughout?
    - Is it a reasonable size?
    - Does it have typical subroutine patterns?
    
    Args:
        rom: ROM data as bytearray
        start: Start offset of potential subroutine
        end: End offset of potential subroutine (exclusive)
        
    Returns:
        Dictionary with validation results
    """
    if end - start < 3:
        return {
            'is_valid': False,
            'reason': 'Too small to be a subroutine',
            'confidence': 0.0
        }
    
    if end - start > 500:
        return {
            'is_valid': False,
            'reason': 'Too large to be a typical subroutine',
            'confidence': 0.0
        }
    
    # Scan through the region
    pc = start
    has_rts_rti = False
    invalid_opcode_count = 0
    total_instructions = 0
    
    # Track instruction types
    loads = 0
    stores = 0
    branches = 0
    jumps = 0
    
    while pc < end and pc < len(rom):
        opcode = rom[pc]
        
        if opcode not in OPCODES:
            invalid_opcode_count += 1
            pc += 1
            continue
        
        mnemonic, size, mode = OPCODES[opcode]
        total_instructions += 1
        
        # Track instruction types
        if mnemonic in ['LDA', 'LDX', 'LDY']:
            loads += 1
        elif mnemonic in ['STA', 'STX', 'STY']:
            stores += 1
        elif mnemonic in ['BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ']:
            branches += 1
        elif mnemonic in ['JMP', 'JSR']:
            jumps += 1
        
        # Check for subroutine terminator
        if mnemonic in ['RTS', 'RTI']:
            has_rts_rti = True
        
        pc += size
    
    # Calculate validation score
    confidence = 0.0
    reasons = []
    
    # Check for invalid opcodes (should be very rare in real code)
    if invalid_opcode_count > 0:
        invalid_ratio = invalid_opcode_count / (total_instructions + invalid_opcode_count)
        if invalid_ratio > 0.1:  # More than 10% invalid
            return {
                'is_valid': False,
                'reason': f'Too many invalid opcodes ({invalid_opcode_count}/{total_instructions + invalid_opcode_count})',
                'confidence': 0.0
            }
        confidence -= invalid_ratio * 0.5
    
    # Check for RTS/RTI (very important for subroutines)
    if has_rts_rti:
        confidence += 0.4
        reasons.append('Has RTS/RTI')
    else:
        confidence -= 0.3
        reasons.append('Missing RTS/RTI')
    
    # Check for reasonable instruction mix
    if total_instructions > 0:
        load_ratio = loads / total_instructions
        store_ratio = stores / total_instructions
        branch_ratio = branches / total_instructions
        
        # Typical code has some loads and stores
        if load_ratio > 0.1:
            confidence += 0.2
            reasons.append('Has load operations')
        
        if store_ratio > 0.05:
            confidence += 0.1
            reasons.append('Has store operations')
        
        # Branches are common in real code
        if branch_ratio > 0.05:
            confidence += 0.15
            reasons.append('Has branches')
        
        # Too many jumps is suspicious (more than 20%)
        jump_ratio = jumps / total_instructions
        if jump_ratio > 0.2:
            confidence -= 0.2
            reasons.append('Unusual jump density')
    
    # Check instruction density (should be reasonable)
    bytes_analyzed = end - start
    if total_instructions > 0:
        avg_instruction_size = bytes_analyzed / total_instructions
        if 1.5 <= avg_instruction_size <= 2.5:  # Typical for 6502
            confidence += 0.15
            reasons.append('Good instruction density')
    
    # Final validation
    is_valid = confidence >= 0.3 and has_rts_rti
    
    return {
        'is_valid': is_valid,
        'confidence': confidence,
        'reasons': reasons,
        'stats': {
            'size': end - start,
            'instructions': total_instructions,
            'loads': loads,
            'stores': stores,
            'branches': branches,
            'jumps': jumps,
            'invalid_opcodes': invalid_opcode_count
        }
    }

def analyze_dead_code(rom: bytearray, code_addresses: Set[int], reachable_addresses: Set[int], base_addr: int) -> Dict:
    """
    Analyze ROM for dead/unreachable code regions.
    
    Args:
        rom: ROM data as bytearray
        code_addresses: Set of all offsets identified as code
        reachable_addresses: Set of offsets reachable from entry points
        base_addr: Base address where ROM is loaded
        
    Returns:
        Dictionary with analysis results
    """
    islands = find_code_islands(rom, code_addresses, reachable_addresses)
    
    results = {
        'islands': [],
        'valid_orphans': [],
        'invalid_orphans': [],
        'total_unreachable_bytes': len(code_addresses - reachable_addresses)
    }
    
    for start, end in islands:
        validation = validate_subroutine(rom, start, end)
        
        island_info = {
            'start_offset': start,
            'end_offset': end,
            'start_addr': base_addr + start,
            'end_addr': base_addr + end - 1,
            'size': end - start,
            'validation': validation
        }
        
        results['islands'].append(island_info)
        
        if validation['is_valid']:
            results['valid_orphans'].append(island_info)
        else:
            results['invalid_orphans'].append(island_info)
    
    return results

def print_dead_code_report(analysis: Dict) -> None:
    """
    Print a formatted report of dead code analysis.
    
    Args:
        analysis: Dictionary from analyze_dead_code()
    """
    print(f"\n=== Dead Code Analysis ===")
    print(f"Total unreachable code bytes: {analysis['total_unreachable_bytes']}")
    print(f"Code islands found: {len(analysis['islands'])}")
    print(f"  Valid orphaned subroutines: {len(analysis['valid_orphans'])}")
    print(f"  Invalid/data regions: {len(analysis['invalid_orphans'])}")
    
    if analysis['valid_orphans']:
        print(f"\nOrphaned Subroutines (unreachable but valid):")
        for island in analysis['valid_orphans']:
            print(f"  ${island['start_addr']:04X}-${island['end_addr']:04X} ({island['size']} bytes)")
            print(f"    Confidence: {island['validation']['confidence']:.2f}")
            print(f"    Reasons: {', '.join(island['validation']['reasons'])}")
            stats = island['validation']['stats']
            print(f"    Stats: {stats['instructions']} instr, {stats['loads']} loads, {stats['stores']} stores, {stats['branches']} branches")
    
    if analysis['invalid_orphans']:
        print(f"\nInvalid Unreachable Regions (likely data misidentified as code):")
        for island in analysis['invalid_orphans']:
            print(f"  ${island['start_addr']:04X}-${island['end_addr']:04X} ({island['size']} bytes)")
            print(f"    Reason: {island['validation']['reason']}")

def get_orphaned_subroutines(analysis: Dict) -> Set[int]:
    """
    Get set of start addresses for valid orphaned subroutines.
    
    These can be added as entry points for disassembly to ensure they're
    properly analyzed and labeled.
    
    Args:
        analysis: Dictionary from analyze_dead_code()
        
    Returns:
        Set of ROM offsets for orphaned subroutine start points
    """
    return {island['start_offset'] for island in analysis['valid_orphans']}

def reclassify_invalid_regions(analysis: Dict, code_addresses: Set[int]) -> Set[int]:
    """
    Remove invalid regions from code_addresses (reclassify as data).
    
    Args:
        analysis: Dictionary from analyze_dead_code()
        code_addresses: Set of offsets identified as code (will be modified)
        
    Returns:
        Set of offsets that were reclassified from code to data
    """
    reclassified = set()
    
    for island in analysis['invalid_orphans']:
        # Remove this island from code_addresses
        for offset in range(island['start_offset'], island['end_offset']):
            if offset in code_addresses:
                code_addresses.remove(offset)
                reclassified.add(offset)
    
    return reclassified

