import sys

from rpython.rlib import longlong2float
from rpython.rlib.unroll import unrolling_iterable
from rpython.rlib.rarithmetic import r_singlefloat, widen
from rpython.rtyper.tool.rfficache import sizeof_c_type
from rpython.rtyper.lltypesystem import lltype, rffi

from hippy.builtin import wrap, StringArg

from rpython.rlib.rarithmetic import intmask


float_buf = lltype.malloc(
    rffi.FLOATP.TO, 1, flavor='raw', immortal=True)

double_buf = lltype.malloc(
    rffi.DOUBLEP.TO, 1, flavor='raw', immortal=True)


class FormatException(Exception):
    def __init__(self, message, char=''):
        self.message = message
        self.char = char


class FmtDesc(object):
    def __init__(self, fmtchar, attrs):
        self.fmtchar = fmtchar
        self.alignment = 1
        self.signed = False
        self.needcount = False
        self.bigendian = False
        self.__dict__.update(attrs)

    def _freeze_(self):
        return True


def table2desclist(table):
    items = table.items()
    items.sort()
    lst = [FmtDesc(key, attrs) for key, attrs in items]
    return unrolling_iterable(lst)


# Pack Methods

def _pack_string(pack_obj, fmtdesc, count, pad):

    if pack_obj.arg_index >= len(pack_obj.arg_w):
        raise FormatException("not enough arguments")

    string = pack_obj.space.str_w(pack_obj.arg_w[pack_obj.arg_index])
    pack_obj.arg_index += 1

    if len(string) < count:
        pack_obj.result.extend(list(string))
        if count != sys.maxint:
            pack_obj.result.extend(list(pad * (count - len(string))))
    else:
        pack_obj.result.extend(list(string[0:count]))


def pack_Z_nul_padded_string(pack_obj, fmtdesc, count):
    if pack_obj.arg_index >= len(pack_obj.arg_w):
        raise FormatException("not enough arguments")

    string = pack_obj.space.str_w(
        pack_obj.arg_w[pack_obj.arg_index])[:count - 1]
    pack_obj.arg_index += 1

    pack_obj.result.extend(list(string) + ['\x00'])

    if len(pack_obj.result) < count:
        pack_obj.result.extend(list('\x00' * (count - len(string) - 1)))


def pack_nul_padded_string(pack_obj, fmtdesc, count):
    _pack_string(pack_obj, fmtdesc, count, '\x00')


def pack_space_padded_string(pack_obj, fmtdesc, count):
    _pack_string(pack_obj, fmtdesc, count, ' ')


def _pack_hex_string(pack_obj, fmtdesc, count, nibbleshift):

    if pack_obj.arg_index >= len(pack_obj.arg_w):
        raise FormatException("not enough arguments")

    string = pack_obj.space.str_w(pack_obj.arg_w[pack_obj.arg_index])
    pack_obj.arg_index += 1

    if len(string) < count:
        raise FormatException("not enough characters in string")

    output = range((len(string) + (len(string) % 2)) / 2)

    value = 0
    first = 1
    outputpos = 0

    for element in string:

        o_element = ord(element)

        o_0, o_9 = ord('0'), ord('9')
        o_A, o_F = ord('A'), ord('F')
        o_a, o_f = ord('a'), ord('f')

        if o_0 <= o_element <= o_9:
            digit = o_element - o_0

        elif o_A <= o_element <= o_F:
            digit = o_element - o_A + 10

        elif o_a <= o_element <= o_f:
            digit = o_element - o_a + 10

        else:
            raise FormatException("illegal hex digit %s" % element)

        value = (value << 4 | digit)
        c = (value & 0xf) << nibbleshift | (value & 0xf0) >> nibbleshift

        if first:
            output[outputpos] = c
            first -= 1
            outputpos += 1
        else:
            output[outputpos-1] = c
            first += 1
            value = 0

        nibbleshift = (nibbleshift + 4) & 7

    for o in output:
        pack_obj.result.append(chr(o))


def pack_hex_string_low_nibble_first(pack_obj, fmtdesc, count):
    _pack_hex_string(pack_obj, fmtdesc, count, 0)


def pack_hex_string_high_nibble_first(pack_obj, fmtdesc, count):
    _pack_hex_string(pack_obj, fmtdesc, count, 4)


def pack_int(pack_obj, fmtdesc, count):

    for _ in range(count):

        if pack_obj.arg_index >= len(pack_obj.arg_w):
            raise FormatException("too few arguments")

        value = pack_obj.space.int_w(
            pack_obj.arg_w[pack_obj.arg_index])

        pack_obj.arg_index += 1

        if fmtdesc.bigendian:
            iterable = range(fmtdesc.size-1, -1, -1)
        else:
            iterable = range(fmtdesc.size)

        for i in iterable:
            if fmtdesc.bigendian:
                x = (value >> (8*i)) & 0xff
                pack_obj.result.append(chr(x))
            else:
                pack_obj.result.append(chr(value & 0xff))
                value >>= 8


def pack_float(pack_obj, fmtdesc, count):

    for _ in range(count):

        if pack_obj.arg_index >= len(pack_obj.arg_w):
            raise FormatException("too few arguments")

        value = pack_obj.space.float_w(
            pack_obj.arg_w[pack_obj.arg_index])
        pack_obj.arg_index += 1

        floatval = r_singlefloat(value)
        value = longlong2float.singlefloat2uint(floatval)
        value = widen(value)

        for i in range(fmtdesc.size):
            pack_obj.result.append(chr(value & 0xff))
            value >>= 8


def pack_double(pack_obj, fmtdesc, count):

    for _ in range(count):

        if pack_obj.arg_index >= len(pack_obj.arg_w):
            raise FormatException("too few arguments")

        value = pack_obj.space.float_w(
            pack_obj.arg_w[pack_obj.arg_index])
        pack_obj.arg_index += 1

        value = longlong2float.float2longlong(value)

        for i in range(fmtdesc.size):
            pack_obj.result.append(chr(value & 0xff))
            value >>= 8


def pack_nul_byte(pack_obj, fmtdesc, count):

    if count == sys.maxint:
        raise FormatException(pack_obj.space, "'*' ignored")

    for _ in range(count):
        pack_obj.result.append(chr(0x00))
        pack_obj.arg_index += 1


def pack_back_up_one_byte(pack_obj, fmtdesc, count):

    if count == sys.maxint:
        raise FormatException("'*' ignored")

    if pack_obj.result:
        pack_obj.result.pop()
        pack_obj.arg_index -= 1
    else:
        raise FormatException("outside of string")


def pack_nullfill_to_absolute_position(pack_obj, fmtdesc, count):

    if count == sys.maxint:
        raise FormatException("'*' ignored")

    if len(pack_obj.result) <= pack_obj.arg_index:
        pack_obj.result.extend(list(chr(0x00) * count))
    else:
        lenght_diff = count - len(pack_obj.result)
        if lenght_diff > 0:
            for _ in range(lenght_diff):
                pack_obj.result.append(chr(0x00))
        if lenght_diff < 0:
            for _ in range(lenght_diff * -1):
                pack_obj.result.pop()


# Unpack Methods

def unpack_nul_padded_string(unpack_obj, fmtdesc, count, name):

    data = []
    for _ in range(count):

        if unpack_obj.string_index >= len(unpack_obj.string):
            raise FormatException(
                "not enough input, need %s, have %s" % (count, len(data)),
                fmtdesc.fmtchar
            )

        data.append(unpack_obj.string[unpack_obj.string_index])
        unpack_obj.string_index += 1

    unpack_obj.result.append(('1%s' % name, "".join(data)))


def unpack_space_padded_string(unpack_obj, fmtdesc, count, name):

    data = []
    for _ in range(count):

        if unpack_obj.string_index >= len(unpack_obj.string):
            raise FormatException(
                "not enough input, need %s, have %s" % (count, len(data)),
                fmtdesc.fmtchar
            )

        element = unpack_obj.string[unpack_obj.string_index]
        unpack_obj.string_index += 1

        data.append(element)

    while data:
        if data[-1] in ['\x00', ' ', '\t', '\r', '\n']:
            data.pop()
        else:
            break

    unpack_obj.result.append(('1%s' % name, "".join(data)))


def unpack_nul_padded_string_2(unpack_obj, fmtdesc, count, name):

    data = []
    for _ in range(count):

        if unpack_obj.string_index >= len(unpack_obj.string):
            raise FormatException(
                "not enough input, need %s, have %s" % (count, len(data)),
                fmtdesc.fmtchar
            )

        element = unpack_obj.string[unpack_obj.string_index]
        unpack_obj.string_index += 1

        if element == '\x00':
            break

        data.append(element)

    unpack_obj.result.append(('1%s' % name, "".join(data)))


hex_digit = ['0', '1', '2', '3',
             '4', '5', '6', '7',
             '8', '9', 'a', 'b',
             'c', 'd', 'e', 'f']


def unpack_hex_string(unpack_obj, fmtdesc, count, name,
                      high_nibble_first=False):

    data = []
    count = count / 2 + count % 2

    for _ in range(count):

        if unpack_obj.string_index >= len(unpack_obj.string):
            raise FormatException(
                "not enough input, need %s, have %s" % (count, len(data)),
                fmtdesc.fmtchar
            )

        element = ord(unpack_obj.string[unpack_obj.string_index])

        unpack_obj.string_index += 1

        nibbles = element % 16, element / 16
        if high_nibble_first:
            nibbles = nibbles[::-1]

        nibbles_digits = hex_digit[nibbles[0]], hex_digit[nibbles[1]]

        if nibbles[-1]:
            data.append('%s%s' % nibbles_digits)
        else:
            data.append(nibbles_digits[0])

    unpack_obj.result.append(("1%s" % name, "".join(data)))


def unpack_hex_string_low_nibble_first(unpack_obj, fmtdesc, count, name):
    unpack_hex_string(unpack_obj, fmtdesc, count, name)


def unpack_hex_string_high_nibble_first(unpack_obj, fmtdesc, count, name):
    unpack_hex_string(unpack_obj, fmtdesc, count, name, True)


def unpack_int(unpack_obj, fmtdesc, count, name):
    result = []
    for pos in range(count):

        data = unpack_obj.string[
            unpack_obj.string_index:unpack_obj.string_index+fmtdesc.size
        ]

        if not len(data) == fmtdesc.size:
            raise FormatException(
                "not enough input, "
                "need %s, have %s" % (fmtdesc.size, len(data)),
                fmtdesc.fmtchar
            )

        unpack_obj.string_index += fmtdesc.size
        value = 0

        if fmtdesc.bigendian:
            for i in range(fmtdesc.size):
                byte = ord(data[i])
                if fmtdesc.signed and i == 0 and byte > 128:
                    byte -= 256
                value |= byte << (fmtdesc.size-1-i) * 8
        else:
            for i in range(fmtdesc.size):
                byte = ord(data[i])
                if fmtdesc.signed and i == fmtdesc.size - 1 and byte > 128:
                    byte -= 256
                value |= byte << i*8

        result.append((("%s%s" % (name, pos+1)), intmask(value)))

    unpack_obj.result.extend(result)


def unpack_signed_char(unpack_obj, fmtdesc, count):
    pass


def unpack_float(unpack_obj, fmtdesc, count, name):

    result = []
    for pos in range(count):

        data = unpack_obj.string[
            unpack_obj.string_index:unpack_obj.string_index+fmtdesc.size
        ]

        if not len(data) == fmtdesc.size:
            raise FormatException(
                "not enough input, "
                "need %s, have %s" % (fmtdesc.size, len(data)),
                fmtdesc.fmtchar
            )

        unpack_obj.string_index += fmtdesc.size

        p = rffi.cast(rffi.CCHARP, float_buf)

        for i, element in enumerate(data[fmtdesc.size*-1:]):
            p[i] = element

        floatval = float_buf[0]
        result.append((("%s%s" % (name, pos+1)), float(floatval)))

    unpack_obj.result.extend(result)


def unpack_double(unpack_obj, fmtdesc, count, name):

    result = []
    for pos in range(count):

        data = unpack_obj.string[
            unpack_obj.string_index:unpack_obj.string_index+fmtdesc.size
        ]

        if not len(data) == fmtdesc.size:
            raise FormatException(
                "not enough input, "
                "need %s, have %s" % (fmtdesc.size, len(data)),
                fmtdesc.fmtchar
            )

        unpack_obj.string_index += fmtdesc.size

        p = rffi.cast(rffi.CCHARP, double_buf)

        for i, element in enumerate(data[fmtdesc.size*-1:]):
            p[i] = element

        value = double_buf[0]
        result.append((("%s%s" % (name, pos+1)), value))

    unpack_obj.result.extend(result)


def unpack_nul_byte(space, data, result, fmtdesc, count):
     # Do nothing with input, just skip it
    pass


def unpack_back_up_one_byte(unpack_obj, fmtdesc, count, name):
    unpack_obj.string_index -= count
    if unpack_obj.string_index < 0:
        unpack_obj.string_index = 0


def unpack_nullfill_to_absolute_position(unpack_obj, fmtdesc, count, name):
    unpack_obj.string_index += count


fmt_table = {
    'a': {
        'size' : 1,
        'pack' : pack_nul_padded_string,
        'unpack' : unpack_nul_padded_string
    },
    'A': {
        'size' : 1,
        'pack' : pack_space_padded_string,
        'unpack' : unpack_space_padded_string
    },
    'h': {
        'size' : 1,
        'pack' : pack_hex_string_low_nibble_first,
        'unpack' : unpack_hex_string_low_nibble_first
    },
    'Z': {
        'size' : 1,
        'pack' : pack_Z_nul_padded_string,
        'unpack' : unpack_nul_padded_string_2
    },
    'H': {
        'size' : 1,
        'pack' : pack_hex_string_high_nibble_first,
        'unpack' : unpack_hex_string_high_nibble_first
    },
    'c': {
        'size' : 1,
        'pack' : pack_int,
        'unpack' : unpack_int,
        'signed' : True,
    },
    'C': {
        'size' : 1,
        'pack' : pack_int,
        'unpack' : unpack_int,
    },
    's': {
        'size' : 2,
        'pack' : pack_int,
        'unpack' : unpack_int,
        'signed' : True,
    },
    'S': {
        'size' : 2,
        'pack' : pack_int,
        'unpack' : unpack_int,
    },
    'n': {
        'size' : 2,
        'pack' : pack_int,
        'unpack' : unpack_int,
        'bigendian': True,
    },
    'v': {
        'size' : 2,
        'pack' : pack_int,
        'unpack' : unpack_int,
        'bigendian': False,
    },
    'i': {
        'size' : sizeof_c_type('unsigned int'),
        'pack' : pack_int,
        'unpack' : unpack_int,
        'signed' : True,
    },
    'I': {
        'size' : 4,
        'pack' : pack_int,
        'unpack' : unpack_int,
    },
    'l': {
        'size' : 4,
        'pack' : pack_int,
        'unpack' : unpack_int,
        'signed': True
    },
    'L': {
        'size' : 4,
        'pack' : pack_int,
        'unpack' : unpack_int,
    },
    'N': {
        'size' : 4,
        'pack' : pack_int,
        'unpack' : unpack_int,
        'bigendian': True,
    },
    'V': {
        'size' : 4,
        'pack' : pack_int,
        'unpack' : unpack_int,
    },
    'f': {
        'size' : sizeof_c_type('float'),
        'pack' : pack_float,
        'unpack' : unpack_float
    },
    'd': {
        'size' : sizeof_c_type('double'),
        'pack' : pack_double,
        'unpack' : unpack_double
    },
    'x': {
        'size' : 1,
        'pack' : pack_nul_byte,
        'unpack' : unpack_nul_byte
    },
    'X': {
        'size' : 1,
        'pack' : pack_back_up_one_byte,
        'unpack' : unpack_back_up_one_byte
    },
    '@': {
        'size' : 1,
        'pack' : pack_nullfill_to_absolute_position,
        'unpack' : unpack_nullfill_to_absolute_position
    },

}

unroll_fmttable = table2desclist(fmt_table)


class Pack(object):

    def __init__(self, space, fmt, arg_w):
        self.space = space
        self.fmt = fmt
        self.table = unroll_fmttable

        self.arg_w = arg_w
        self.arg_index = 0

    def _size(self, fmt_interpreted):
        size = 0
        for fmtdesc, repetitions in self.fmt_interpreted:
            size += fmtdesc.size * repetitions
        return size

    def _get_fmtdesc(self, char):
        # for fmtdesc in self.table:
        #     if char == fmtdesc.fmtchar:
        #         return fmtdesc
        try:
            assert isinstance(char, str)
            d = fmt_table[char]
            return None
            # return FmtDesc(char, d)
        except KeyError:
            return None

    def interpret(self):
        results = []
        from rpython.rlib.rsre.rsre_re import finditer
        itr = finditer('((\S)(\d+|\*)?)', self.fmt)
        try:
            while True:
                _, char, repetitions = itr.next().groups()
                fmtdesc = self._get_fmtdesc(char)
                if repetitions is None:
                    repetitions = 1
                if repetitions == '*':
                    repetitions = sys.maxint
                results.append((fmtdesc, int(repetitions)))
        except StopIteration:
            pass
        return results


    def build(self):
        self.fmt_interpreted = self.interpret()
        self.size = self._size(self.fmt_interpreted)

        self.result = []

        for fmtdesc, repetitions in self.fmt_interpreted:

            try:
                fmtdesc.pack(self, fmtdesc, repetitions)
            except FormatException as e:
                self.space.ec.warn(
                    "pack(): Type %s: %s" % (fmtdesc.fmtchar, e.message)
                )

        if self.arg_index < len(self.arg_w):
            self.space.ec.warn(
                "pack(): %s "
                "arguments unused" % (len(self.arg_w) - self.arg_index)
            )

        return "".join(self.result)


class Unpack(object):

    def __init__(self, fmt, string):
        self.fmt = fmt
        self.string = string
        self.string_index = 0

        self.table = unroll_fmttable
        self.result = []

    def _get_fmtdect(self, char):
        for fmtdesc in self.table:
            if char == fmtdesc.fmtchar:
                return fmtdesc

    def interpret(self):
        results = []
        from rpython.rlib.rsre.rsre_re import finditer
        itr = finditer('((\S)(\d+|\*)?((\/)|(([a-z]+)(\/)?))?)', self.fmt)
        try:
            while True:
                _, char, repetitions, _, _, _, name, _ = itr.next().groups()
                print char, repetitions, name
                if char != '/':
                    fmtdesc = self._get_fmtdect(char)
                    if repetitions is None:
                        repetitions = 1
                    if repetitions == '*':
                        repetitions = sys.maxint
                    if name == '/':
                        name = None
                    results.append((fmtdesc, int(repetitions), name))
        except StopIteration:
            pass
        return results


    # def interpret2(self):
    #     results = []

    #     index = 0
    #     repetitions = 1
    #     fmt = self.fmt
    #     while index < len(fmt):

    #         format_name_elements = []
    #         format_name = ""

    #         element = fmt[index]
    #         index += 1

    #         if element.isspace():
    #             continue

    #         repetitions = None
    #         if index < len(fmt):
    #             assert index >= 0
    #             while index < len(fmt) and fmt[index].isdigit():

    #                 if repetitions is None:
    #                     repetitions = 0

    #                 repetitions = repetitions * 10
    #                 repetitions = repetitions + (
    #                     ord(fmt[index]) - ord('0'))

    #                 index += 1

    #             if repetitions is None and fmt[index] == '*':
    #                 repetitions = sys.maxint
    #                 index += 1

    #         if repetitions is None:
    #             repetitions = 1

    #         while index < len(fmt) and fmt[index] != '/':
    #             format_name_elements.append(fmt[index])
    #             index += 1

    #         format_name = "".join(format_name_elements)

    #         if index < len(fmt) and fmt[index] == '/':
    #             index += 1

    #         for fmtdesc in self.table:
    #             if element == fmtdesc.fmtchar:
    #                 results.append((fmtdesc, repetitions, format_name))
    #                 break
    #     import pdb; pdb.set_trace()
    #     return results

    def build(self):
        self.fmt_interpreted = self.interpret()

        for fmtdesc, repetitions, name in self.fmt_interpreted:
            if repetitions == sys.maxint:
                repetitions = len(self.string) - self.string_index

            fmtdesc.unpack(self, fmtdesc, repetitions, name)
        return self.result


@wrap(['space', StringArg(None), 'args_w'])
def pack(space, formats, args_w):
    results = Pack(space, formats, args_w).build()
    return space.newstr(results)


# @wrap(['space', StringArg(None), StringArg(None)])
def _unpack(space, formats, string):
    try:
        results = Unpack(formats, string).build()
    except FormatException as e:
        space.ec.warn("unpack(): Type %s: %s" % (e.char, e.message))
        return space.w_False

    return space.new_array_from_pairs(
        [(space.wrap(k), space.wrap(v)) for k, v in results])
