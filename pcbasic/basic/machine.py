"""
PC-BASIC - machine.py
Machine emulation and memory model

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import logging

from . import values
from . import devices
from . import error


###############################################################################

class MachinePorts(object):
    """Machine ports."""

    # time delay for port value to drop to 0 on maximum reading.
    #  use 100./255. for 100ms.
    joystick_time_factor = 75. / 255.

    def __init__(self, session):
        """Initialise machine ports."""
        self.session = session
        # parallel port base address:
        # http://retired.beyondlogic.org/spp/parallel.htm
        # 3BCh - 3BFh  Used for Parallel Ports which were incorporated on to Video Cards - Doesn't support ECP addresses
        # 378h - 37Fh  Usual Address For LPT 1
        # 278h - 27Fh  Usual Address For LPT 2
        dev = self.session.devices
        self.lpt_device = [dev.devices['LPT1:'], dev.devices['LPT2:']]
        # serial port base address:
        # http://www.petesqbsite.com/sections/tutorials/zines/qbnews/9-com_ports.txt
        #            COM1             &H3F8
        #            COM2             &H2F8
        #            COM3             &H3E8 (not implemented)
        #            COM4             &H2E8 (not implemented)
        self.com_base = {0x3f8: 0, 0x2f8: 1}
        self.com_device = [dev.devices['COM1:'], dev.devices['COM2:']]
        self.com_enable_baud_write = [False, False]
        self.com_baud_divisor = [0, 0]
        self.com_break = [False, False]

    def usr_(self, num):
        """USR: get value of machine-code function; not implemented."""
        logging.warning('USR function not implemented.')
        return 0

    def inp_(self, num):
        """INP: get value from machine port."""
        port = values.to_int(num, unsigned=True)
        inp = self.inp(port)
        # return as unsigned int
        if inp < 0:
            inp += 0x10000
        return inp

    def inp(self, port):
        """Get the value in an emulated machine port."""
        # keyboard
        if port == 0x60:
            return self.session.keyboard.last_scancode
        # game port (joystick)
        elif port == 0x201:
            value = (
                (not self.session.stick.is_firing[0][0]) * 0x40 +
                (not self.session.stick.is_firing[0][1]) * 0x20 +
                (not self.session.stick.is_firing[1][0]) * 0x10 +
                (not self.session.stick.is_firing[1][1]) * 0x80)
            decay = self.session.stick.decay()
            if decay < self.session.stick.axis[0][0] * self.joystick_time_factor:
                value += 0x04
            if decay < self.session.stick.axis[0][1] * self.joystick_time_factor:
                value += 0x02
            if decay < self.session.stick.axis[1][0] * self.joystick_time_factor:
                value += 0x01
            if decay < self.session.stick.axis[1][1] * self.joystick_time_factor:
                value += 0x08
            return value
        elif port in (0x379, 0x279):
            # parallel port input ports
            # http://www.aaroncake.net/electronics/qblpt.htm
            # http://retired.beyondlogic.org/spp/parallel.htm
            lpt_port_nr = 0 if port >= 0x378 else 1
            base_addr = {0: 0x378, 1: 0x278}
            if self.lpt_device[lpt_port_nr].stream is None:
                return 0
            # get status port
            busy, ack, paper, select, err = self.lpt_device[lpt_port_nr].stream.get_status()
            return busy * 0x80 | ack * 0x40 | paper * 0x20 | select * 0x10 | err * 0x8
        else:
            # serial port machine ports
            # http://www.qb64.net/wiki/index.php/Port_Access_Libraries#Serial_Communication_Registers
            # http://control.com/thread/1026221083
            for base_addr, com_port_nr in self.com_base.iteritems():
                com_port = self.com_device[com_port_nr]
                if com_port.stream is None:
                    continue
                # Line Control Register: base_address + 3 (r/w)
                if port == base_addr + 3:
                    _, parity, bytesize, stopbits = com_port.stream.get_params()
                    value = self.com_enable_baud_write[com_port_nr] * 0x80
                    value += self.com_break[com_port_nr] * 0x40
                    value += {'S': 0x38, 'M': 0x28, 'E': 0x18, 'O': 0x8, 'N': 0}[parity]
                    if stopbits > 1:
                        value += 0x4
                    value += bytesize - 5
                    return value
                # Line Status Register: base_address + 5 (read only)
                elif port == base_addr + 5:
                    # bit 6: data holding register empty
                    # bit 5: transmitter holding register empty
                    # distinction between bit 5 and 6 not implemented
                    # bit 0: data ready
                    # other bits not implemented:
                    #   1 - overrun, 2 - parity 3 - framing errors;
                    #   4 - break interrupt; 7 - at least one error in received FIFO
                    in_waiting, out_waiting = com_port.stream.io_waiting()
                    return (1-out_waiting) * 0x60 + in_waiting
                # Modem Status Register: base_address + 6 (read only)
                elif port == base_addr + 6:
                    cd, ri, dsr, cts = com_port.stream.get_pins()
                    # delta bits not implemented
                    return (cd*0x80 + ri*0x40 + dsr*0x20 + cts*0x10)
            # addr isn't one of the covered ports
            return 0

    def out_(self, addr, val):
        """Send a value to an emulated machine port."""
        if addr == 0x201:
            # game port reset
            self.session.stick.reset_decay()
        elif addr == 0x3c5:
            # officially, requires OUT &H3C4, 2 first (not implemented)
            self.session.screen.mode.set_plane_mask(val)
        elif addr == 0x3cf:
            # officially, requires OUT &H3CE, 4 first (not implemented)
            self.session.screen.mode.set_plane(val)
        elif addr == 0x3d8:
            #OUT &H3D8,&H1A: REM enable color burst
            #OUT &H3D8,&H1E: REM disable color burst
            # 0x1a == 0001 1010     0x1e == 0001 1110
            self.session.screen.set_colorburst(val & 4 == 0)
        elif addr in (0x378, 0x37A, 0x278, 0x27A):
            # parallel port output ports
            # http://www.aaroncake.net/electronics/qblpt.htm
            # http://retired.beyondlogic.org/spp/parallel.htm
            lpt_port_nr = 0 if addr >= 0x378 else 1
            base_addr = {0: 0x378, 1: 0x278}
            if self.lpt_device[lpt_port_nr].stream is None:
                return
            if addr - base_addr[lpt_port_nr] == 0:
                # set data port
                self.lpt_device[lpt_port_nr].stream.write(chr(val))
            else:
                # set control port
                self.lpt_device[lpt_port_nr].stream.set_control(
                    select=val & 0x8, init=val&0x4, lf=val&0x2, strobe=val&0x1)
        else:
            # serial port machine ports
            # http://www.qb64.net/wiki/index.php/Port_Access_Libraries#Serial_Communication_Registers
            # http://control.com/thread/1026221083
            for base_addr, com_port_nr in self.com_base.iteritems():
                com_port = self.com_device[com_port_nr]
                if com_port.stream is None:
                    continue
                # ports at base addr and the next one are used for writing baud rate
                # (among other things that aren't implemented)
                if addr in (base_addr, base_addr+1) and self.com_enable_baud_write[com_port_nr]:
                    if addr == base_addr:
                        self.com_baud_divisor[com_port_nr] = (self.com_baud_divisor[com_port_nr] & 0xff00) + val
                    elif addr == base_addr + 1:
                        self.com_baud_divisor[com_port_nr] = val*0x100 + (self.com_baud_divisor[com_port_nr] & 0xff)
                    if self.com_baud_divisor[com_port_nr]:
                        baudrate, parity, bytesize, stopbits = com_port.stream.get_params()
                        baudrate = 115200 // self.com_baud_divisor[com_port_nr]
                        com_port.stream.set_params(baudrate, parity, bytesize, stopbits)
                # Line Control Register: base_address + 3 (r/w)
                elif addr == base_addr + 3:
                    baudrate, parity, bytesize, stopbits = com_port.stream.get_params()
                    if val & 0x80:
                        self.com_enable_baud_write[com_port_nr] = True
                    # break condition
                    self.com_break[com_port_nr] = (val & 0x40) != 0
                    # parity
                    parity = {0x38:'S', 0x28:'M', 0x18:'E', 0x8:'O', 0:'N'}[val&0x38]
                    # stopbits
                    if val & 0x4:
                        # 2 or 1.5 stop bits
                        stopbits = 2
                    else:
                        # 1 stop bit
                        stopbits = 1
                    # set byte size to 5, 6, 7, 8
                    bytesize = (val & 0x3) + 5
                    com_port.stream.set_params(baudrate, parity, bytesize, stopbits)
                    com_port.stream.set_pins(brk=self.com_break[com_port_nr])
                # Modem Control Register: base_address + 4 (r/w)
                elif addr == base_addr + 4:
                    com_port.stream.set_pins(rts=val & 0x2, dtr=val & 0x1)

    def wait_(self, addr, ander, xorer):
        """Wait untial an emulated machine port has a specified value."""
        with self.session.events.suspend():
            while (self.inp(addr) ^ xorer) & ander == 0:
                self.session.events.wait()



###############################################################################
# Memory

class Memory(object):
    """Memory model."""

    # lowest (EGA) video memory address; max 128k reserved for video
    video_segment = 0xa000
    # read only memory
    rom_segment = 0xf000
    # segment that holds ram font
    ram_font_segment = 0xc000

    # where to find the rom font (chars 0-127)
    rom_font_addr = 0xfa6e
    # where to find the ram font (chars 128-254)
    ram_font_addr = 0x500

    key_buffer_offset = 30
    blink_enabled = True

    def __init__(self, data_memory, devices, files, screen, keyboard,
                font_8, interpreter, peek_values, syntax):
        """Initialise memory."""
        # data segment initialised elsewhere
        self.data = data_memory
        # device access needed for COM and LPT ports
        self.devices = devices
        # for BLOAD and BSAVE
        self._files = files
        # screen access needed for video memory
        self.screen = screen
        # keyboard buffer access
        self.keyboard = keyboard
        # interpreter, for runmode check
        self.interpreter = interpreter
        # 8-pixel font
        self.font_8 = font_8
        # initial DEF SEG
        self.segment = self.data.data_segment
        # pre-defined PEEK outputs
        self._peek_values = {}
        # tandy syntax
        self.tandy_syntax = syntax == 'tandy'

    def peek_(self, addr):
        """PEEK: Retrieve the value at an emulated memory location."""
        # no peeking the program code (or anywhere) in protected mode
        if self.data.program.protected and not self.interpreter.run_mode:
            raise error.RunError(error.IFC)
        addr = values.to_int(addr, unsigned=True)
        addr += self.segment * 0x10
        return self._get_memory(addr)

    def poke_(self, args):
        """POKE: Set the value at an emulated memory location."""
        addr = values.to_int(next(args), unsigned=True)
        if self.data.program.protected and not self.interpreter.run_mode:
            raise error.RunError(error.IFC)
        val, = args
        val = values.to_int(val)
        error.range_check(0, 255, val)
        if addr < 0:
            addr += 0x10000
        addr += self.segment * 0x10
        self._set_memory(addr, val)

    def bload_(self, args):
        """BLOAD: Load a file into a block of memory."""
        if self.data.program.protected and not self.interpreter.run_mode:
            raise error.RunError(error.IFC)
        name = next(args)
        offset = next(args)
        if offset is not None:
            offset = values.to_int(offset, unsigned=True)
        list(args)
        with self._files.open(0, name, filetype='M', mode='I') as g:
            # size gets ignored; even the \x1a at the end gets dumped onto the screen.
            seg = g.seg
            if offset is None:
                offset = g.offset
            buf = bytearray(g.read())
            # remove any EOF marker at end
            if buf and buf[-1] == 0x1a:
                buf = buf[:-1]
            # Tandys repeat the header at the end of the file
            if self.tandy_syntax:
                buf = buf[:-7]
            addr = seg * 0x10 + offset
            self._set_memory_block(addr, buf)

    def bsave_(self, args):
        """BSAVE: Save a block of memory into a file."""
        if self.data.program.protected and not self.interpreter.run_mode:
            raise error.RunError(error.IFC)
        name = next(args)
        offset = values.to_int(next(args), unsigned=True)
        length = values.to_int(next(args), unsigned=True)
        list(args)
        with self._files.open(0, name, filetype='M', mode='O',
                    seg=self.segment, offset=offset, length=length) as g:
            addr = self.segment * 0x10 + offset
            g.write(str(self._get_memory_block(addr, length)))
            # Tandys repeat the header at the end of the file
            if self.tandy_syntax:
                g.write(devices.type_to_magic['M'] +
                        struct.pack('<HHH', self.segment, offset, length))

    def def_seg_(self, segment=None):
        """DEF SEG: Set segment."""
        # &hb800: text screen buffer; &h13d: data segment
        if segment is None:
            self.segment = self.data.data_segment
        else:
            self.segment = segment
            if self.segment < 0:
                self.segment += 0x10000

    def def_usr_(self, usr, addr):
        """DEF USR: Define machine language function."""
        logging.warning('DEF USR statement not implemented')

    def call_(self, args):
        """CALL: Call machine language procedure."""
        addr_var = next(args)
        if addr_var[-1] == values.STR:
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        list(args)
        logging.warning('CALL/CALLS statement not implemented')

    ###########################################################################
    # IMPLEMENTATION

    def _get_memory(self, addr):
        """Retrieve the value at an emulated memory location."""
        try:
            # try if there's a preset value
            return self._peek_values[addr]
        except KeyError:
            if addr >= self.rom_segment*0x10:
                # ROM font
                return max(0, self._get_rom_memory(addr))
            elif addr >= self.ram_font_segment*0x10:
                # RAM font
                return max(0, self._get_font_memory(addr))
            elif addr >= self.video_segment*0x10:
                # graphics and text memory
                return max(0, self._get_video_memory(addr))
            elif addr >= self.data.data_segment*0x10:
                return max(0, self.data.get_memory(addr))
            elif addr >= 0:
                return max(0, self._get_low_memory(addr))
            else:
                return 0

    def _set_memory(self, addr, val):
        """Set the value at an emulated memory location."""
        if addr >= self.rom_segment*0x10:
            # ROM includes font memory
            pass
        elif addr >= self.ram_font_segment*0x10:
            # RAM font memory
            self._set_font_memory(addr, val)
        elif addr >= self.video_segment*0x10:
            # graphics and text memory
            self._set_video_memory(addr, val)
        elif addr >= self.data.data_segment*0x10:
            self.data.set_memory(addr, val)
        elif addr >= 0:
            self._set_low_memory(addr, val)

    def _get_memory_block(self, addr, length):
        """Retrieve a contiguous block of bytes from memory."""
        block = bytearray()
        if addr >= self.video_segment*0x10:
            video_len = 0x20000 - (addr - self.video_segment*0x10)
            # graphics and text memory - specialised call
            block += self._get_video_memory_block(addr, min(length, video_len))
            addr += video_len
            length -= video_len
        for a in range(addr, addr+length):
            block += chr(max(0, self._get_memory(a)))
        return block

    def _set_memory_block(self, addr, buf):
        """Set a contiguous block of bytes in memory."""
        if addr >= self.video_segment*0x10:
            video_len = 0x20000 - (addr - self.video_segment*0x10)
            # graphics and text memory - specialised call
            self._set_video_memory_block(addr, buf[:video_len])
            addr += video_len
            buf = buf[video_len:]
        for a in range(len(buf)):
            self._set_memory(addr + a, buf[a])


    ###############################################################
    # video memory model

    def _get_video_memory(self, addr):
        """Retrieve a byte from video memory."""
        return self.screen.mode.get_memory(addr, 1)[0]

    def _set_video_memory(self, addr, val):
        """Set a byte in video memory."""
        return self.screen.mode.set_memory(addr, [val])

    def _get_video_memory_block(self, addr, length):
        """Retrieve a contiguous block of bytes from video memory."""
        return bytearray(self.screen.mode.get_memory(addr, length))

    def _set_video_memory_block(self, addr, some_bytes):
        """Set a contiguous block of bytes in video memory."""
        self.screen.mode.set_memory(addr, some_bytes)

    ###############################################################################

    def _get_rom_memory(self, addr):
        """Retrieve data from ROM."""
        addr -= self.rom_segment*0x10 + self.rom_font_addr
        char = addr // 8
        if char > 127 or char<0:
            return -1
        return ord(self.font_8.fontdict[
                self.screen.codepage.to_unicode(chr(char), u'\0')][addr%8])

    def _get_font_memory(self, addr):
        """Retrieve RAM font data."""
        addr -= self.ram_font_segment*0x10 + self.ram_font_addr
        char = addr // 8 + 128
        if char < 128 or char > 254:
            return -1
        return ord(self.font_8.fontdict[
                self.screen.codepage.to_unicode(chr(char), u'\0')][addr%8])

    def _set_font_memory(self, addr, value):
        """Retrieve RAM font data."""
        addr -= self.ram_font_segment*0x10 + self.ram_font_addr
        char = addr // 8 + 128
        if char < 128 or char > 254:
            return
        uc = self.screen.codepage.to_unicode(chr(char))
        if uc:
            old = self.font_8.fontdict[uc]
            self.font_8.fontdict[uc] = old[:addr%8]+chr(value)+old[addr%8+1:]
            self.screen.rebuild_glyph(char)

    #################################################################################


    def _get_low_memory(self, addr):
        """Retrieve data from low memory."""
        addr -= 0
        # from MEMORY.ABC: PEEKs and POKEs (Don Watkins)
        # http://www.qbasicnews.com/abc/showsnippet.php?filename=MEMORY.ABC&snippet=6
        # 108-115 control Ctrl-break capture; not implemented (see PC Mag POKEs)
        if addr == 124:
            return self.ram_font_addr % 256
        elif addr == 125:
            return self.ram_font_addr // 256
        elif addr == 126:
            return self.ram_font_segment % 256
        elif addr == 127:
            return self.ram_font_segment // 256
        # 1040 monitor type
        elif addr == 1040:
            if self.screen.monitor == 'mono':
                # mono
                return 48 + 6
            else:
                # 80x25 graphics
                return 32 + 6
        # http://textfiles.com/programming/peekpoke.txt
        #   "(PEEK (1041) AND 14)/2" WILL PROVIDE NUMBER OF RS232 PORTS INSTALLED.
        #   "(PEEK (1041) AND 16)/16" WILL PROVIDE NUMBER OF GAME PORTS INSTALLED.
        #   "(PEEK (1041) AND 192)/64" WILL PROVIDE NUMBER OF PRINTERS INSTALLED.
        elif addr == 1041:
            return (2 * ((self.devices.devices['COM1:'].stream is not None) +
                        (self.devices.devices['COM2:'].stream is not None)) +
                    16 +
                    64 * ((self.devices.devices['LPT1:'].stream is not None) +
                        (self.devices.devices['LPT2:'].stream is not None) +
                        (self.devices.devices['LPT3:'].stream is not None)))
        # &h40:&h17 keyboard flag
        # &H80 - Insert state active
        # &H40 - CapsLock state has been toggled
        # &H20 - NumLock state has been toggled
        # &H10 - ScrollLock state has been toggled
        # &H08 - Alternate key depressed
        # &H04 - Control key depressed
        # &H02 - Left shift key depressed
        # &H01 - Right shift key depressed
        elif addr == 1047:
            return self.keyboard.mod
        # &h40:&h18 keyboard flag
        # &H80 - Insert key is depressed
        # &H40 - CapsLock key is depressed
        # &H20 - NumLock key is depressed
        # &H10 - ScrollLock key is depressed
        # &H08 - Suspend key has been toggled
        # not implemented: peek(1048)==4 if sysrq pressed, 0 otherwise
        elif addr == 1048:
            return 0
        elif addr == 1049:
            return int(self.keyboard.keypad_ascii or 0)%256
        elif addr == 1050:
            # keyboard ring buffer starts at n+1024; lowest 1054
            return (self.keyboard.buf.start*2 + self.key_buffer_offset) % 256
        elif addr == 1051:
            return (self.keyboard.buf.start*2 + self.key_buffer_offset) // 256
        elif addr == 1052:
            # ring buffer ends at n + 1023
            return (self.keyboard.buf.stop()*2 + self.key_buffer_offset) % 256
        elif addr == 1053:
            return (self.keyboard.buf.stop()*2 + self.key_buffer_offset) // 256
        elif addr in range(1024+self.key_buffer_offset, 1024+self.key_buffer_offset+32):
            index = (addr-1024-self.key_buffer_offset)//2
            odd = (addr-1024-self.key_buffer_offset)%2
            c, scan = self.keyboard.buf.ring_read(index)
            if odd:
                return scan
            elif c == '':
                return 0
            else:
                # however, arrow keys (all extended scancodes?) give 0xe0 instead of 0
                return ord(c[0])
        # 1097 screen mode number
        elif addr == 1097:
            # these are the low-level mode numbers used by mode switching interrupt
            cval = self.screen.colorswitch % 2
            if self.screen.mode.is_text_mode:
                if (self.screen.capabilities in ('mda', 'ega_mono') and
                        self.screen.mode.width == 80):
                    return 7
                return (self.screen.mode.width == 40)*2 + cval
            elif self.screen.mode.name == '320x200x4':
                return 4 + cval
            else:
                mode_num = {'640x200x2': 6, '160x200x16': 8, '320x200x16pcjr': 9,
                    '640x200x4': 10, '320x200x16': 13, '640x200x16': 14,
                    '640x350x4': 15, '640x350x16': 16, '640x400x2': 0x40,
                    '320x200x4pcjr': 4 }
                    # '720x348x2': ? # hercules - unknown
                try:
                    return mode_num[self.screen.mode.name]
                except KeyError:
                    return 0xff
        # 1098, 1099 screen width
        elif addr == 1098:
            return self.screen.mode.width % 256
        elif addr == 1099:
            return self.screen.mode.width // 256
        # 1100, 1101 graphics page buffer size (32k for screen 9, 4k for screen 0)
        # 1102, 1103 zero (PCmag says graphics page buffer offset)
        elif addr == 1100:
            return self.screen.mode.page_size % 256
        elif addr == 1101:
            return self.screen.mode.page_size // 256
        # 1104 + 2*n (cursor column of page n) - 1
        # 1105 + 2*n (cursor row of page n) - 1
        # we only keep track of one row,col position
        elif addr in range(1104, 1120, 2):
            return self.screen.current_col - 1
        elif addr in range(1105, 1120, 2):
            return self.screen.current_row - 1
        # 1120, 1121 cursor shape
        elif addr == 1120:
            return self.screen.cursor.to_line
        elif addr == 1121:
            return self.screen.cursor.from_line
        # 1122 visual page number
        elif addr == 1122:
            return self.screen.vpagenum
        # 1125 screen mode info
        elif addr == 1125:
            # bit 0: only in text mode?
            # bit 2: should this be colorswitch or colorburst_is_enabled?
            return ((self.screen.mode.width == 80) * 1 +
                    (not self.screen.mode.is_text_mode) * 2 +
                     self.screen.colorswitch * 4 + 8 +
                     (self.screen.mode.name == '640x200x2') * 16 +
                     self.blink_enabled * 32)
        # 1126 color
        elif addr == 1126:
            if self.screen.mode.name == '320x200x4':
                return (self.screen.palette.get_entry(0)
                        + 32 * self.screen.cga4_palette_num)
            elif self.screen.mode.is_text_mode:
                return self.screen.border_attr % 16
                # not implemented: + 16 "if current color specified through
                # COLOR f,b with f in [0,15] and b > 7
        # 1296, 1297: zero (PCmag says data segment address)
        return -1

    def _set_low_memory(self, addr, value):
        """Set data in low memory."""
        addr -= 0
        if addr == 1047:
            self.keyboard.mod = value
        # from basic_ref_3.pdf: the keyboard buffer may be cleared with
        # DEF SEG=0: POKE 1050, PEEK(1052)
        elif addr == 1050:
            # keyboard ring buffer starts at n+1024; lowest 1054
            self.keyboard.buf.ring_set_boundaries(
                    (value - self.key_buffer_offset) // 2,
                    self.keyboard.buf.stop())
        elif addr == 1052:
            # ring buffer ends at n + 1023
            self.keyboard.buf.ring_set_boundaries(
                    self.keyboard.buf.start,
                    (value - self.key_buffer_offset) // 2)
        elif addr in range(1024+self.key_buffer_offset, 1024+self.key_buffer_offset+32):
            index = (addr-1024-self.key_buffer_offset)//2
            odd = (addr-1024-self.key_buffer_offset)%2
            c, scan = self.keyboard.buf.ring_read(index)
            if odd:
                scan = value
            elif value in (0, 0xe0):
                c = ''
            else:
                c = chr(value)
            self.keyboard.buf.ring_write(index, c, scan)
