import argparse
import xml.etree.ElementTree as ET
import sys
import copy
import re
from enum import Enum


class VariableType(Enum):
    BOOL = 'bool'
    INT = 'int'
    STRING = 'string'
    NIL = 'nil'
    UNINIT = ''

class VariableData:# actual data with its type
    def __init__(self, typpe, value):
        self.type = typpe
        self.value = value

    @staticmethod
    def empty():
        return VariableData(VariableType.UNINIT, None)

class ErrCode(Enum):
    CMD_ARGS = 10
    OPEN_INPUT_FILE = 11
    FORMAT_XML = 31
    BAD_XML = 32
    SEMANTIC = 52
    OPERAND_TYPE = 53
    NONEXISTS_VAR = 54
    NONEXISTS_FRAME = 55
    UNINITIALIZED_VAR = 56
    OPERAND_VALUE = 57
    BAD_STRING_MANIPULATION = 58


class ErrorHandler:
    @staticmethod
    def error_exit(msg, code):
        sys.stderr.write("<ERROR EXIT> "+msg+"\n")
        sys.exit(code.value)


class ProgramContext:  # holds variable dictionaries, program counter, navigates around the program
    def __init__(self, input_stream):
        self.label_dict = {}
        self.global_var_dict = {}
        self.temporary_var_dict = None
        self.local_var_dict_stack = []
        self.program_counter = 0
        self.input_stream = input_stream
        self.call_program_counter = None
        self.stack = []

    def pushStack(self, data):
        self.stack.append(data)

    def popStack(self):
        if len(self.stack) == 0:
            ErrorHandler.error_exit(
                'pop var stack, empty', ErrCode.UNINITIALIZED_VAR)
        return self.stack.pop()

    def _getVarData(self, frame, name):
        if frame == "GF":
            return self.global_var_dict.get(name)
        elif frame == 'TF':
            if self.temporary_var_dict == None:
                self.nonexists_frame_error(frame)
            return self.temporary_var_dict.get(name)
        elif frame == 'LF':
            if len(self.local_var_dict_stack) == 0:
                self.nonexists_frame_error(frame)
            return self.local_var_dict_stack[-1].get(name)
        else:
            self.nonexists_frame_error(frame)

    def peekVarType(self, frame, name):
        var_data = self._getVarData(frame, name)

        if var_data == None:
            self.nonexists_var_error(frame, name)

        return var_data.type

    def readVariable(self, frame, name):
        var_data = self._getVarData(frame, name)

        if var_data == None:
            self.nonexists_var_error(frame, name)

        if var_data.type == None:
            self.uninit_var_error(frame, name)

        return copy.deepcopy(var_data)

    def writeVariable(self, frame, name, data):
        if frame == "GF":
            if name not in self.global_var_dict.keys():
                self.nonexists_var_error(frame, name)
            self.global_var_dict[name] = data
        elif frame == 'TF':
            if self.temporary_var_dict == None:
                self.nonexists_frame_error(frame)
            if name not in self.temporary_var_dict.keys():
                self.nonexists_var_error(frame, name)
            self.temporary_var_dict[name] = data
        elif frame == 'LF':
            if len(self.local_var_dict_stack) == 0:
                self.nonexists_frame_error(frame)
            if name not in self.local_var_dict_stack[-1].keys():
                self.nonexists_var_error(frame, name)
            self.local_var_dict_stack[-1][name] = data
        else:
            self.label_name_error(frame)

    def label_name_error(self, frame):
        ErrorHandler.error_exit(
            'unknown label name [{}]'.format(frame), ErrCode.SEMANTIC)

    def uninit_var_error(self, frame, name):
        ErrorHandler.error_exit('uninitialized var [{},{}]'.format(
            frame, name), ErrCode.UNINITIALIZED_VAR)

    def nonexists_var_error(self, frame, name):
        ErrorHandler.error_exit(
            'undefined var [{}, {}]'.format(frame, name), ErrCode.NONEXISTS_VAR)

    def nonexists_frame_error(self, frame):
        ErrorHandler.error_exit('nonexists frame [{}]'.format(
            frame), ErrCode.NONEXISTS_FRAME)

    def var_redef_error(self, frame, name):
        ErrorHandler.error_exit(
            'variable redefinition [{}, {}]'.format(frame, name), ErrCode.SEMANTIC)

    def declareVariable(self, frame, name):
        if frame == "GF":
            if name in self.global_var_dict.keys():
                self.var_redef_error(frame, name)
            self.global_var_dict[name] = VariableData.empty()
        elif frame == 'TF':
            if self.temporary_var_dict == None:
                self.nonexists_frame_error(frame)
            if name in self.temporary_var_dict.keys():
                self.var_redef_error(frame, name)
            self.temporary_var_dict[name] = VariableData.empty()
        elif frame == 'LF':
            if len(self.local_var_dict_stack) == 0:
                self.nonexists_frame_error(frame)
            if name in self.local_var_dict_stack[-1].keys():
                self.var_redef_error(frame, name)
            self.local_var_dict_stack[-1][name] = VariableData.empty()
        else:
            self.label_name_error(frame)

    def declareLabel(self, label):
        if label in self.label_dict.keys():
            ErrorHandler.error_exit(
                'label redeclaration [{}]'.format(label), ErrCode.SEMANTIC)
        self.label_dict[label] = self.program_counter

    def jumpLabel(self, label):
        if label not in self.label_dict.keys():
            ErrorHandler.error_exit(
                'label is undefined [{}]'.format(label), ErrCode.SEMANTIC)
        self.program_counter = self.label_dict[label]

    def callLabel(self, label):
        self.call_program_counter = self.program_counter
        self.jumpLabel(label)

    def returnLabel(self):
        if self.call_program_counter != None:
            self.program_counter = self.call_program_counter
            self.call_program_counter = None
        else:
            ErrorHandler.error_exit(
                'return label empty call stack', ErrCode.UNINITIALIZED_VAR)  # TODO is this right?

    def createFrame(self):
        self.temporary_var_dict = {}

    def pushFrame(self):
        if self.temporary_var_dict == None:
            self.nonexists_frame_error('TF')
        self.local_var_dict_stack.append(
            copy.deepcopy(self.temporary_var_dict))
        self.temporary_var_dict = None

    def popFrame(self):
        if len(self.local_var_dict_stack) == 0:
            self.nonexists_frame_error('LF')
        self.temporary_var_dict = self.local_var_dict_stack.pop()


class ArgumentXML:#argument parsed from xml
    def __init__(self, typpe, textval):
        self.typename = typpe
        self.textval = textval


class Arg_Symb:
    def __init__(self):
        pass


class Arg_Var(Arg_Symb):
    def __init__(self, name, frame):
        self.name = name
        self.frame = frame


class Arg_Literal(Arg_Symb):
    def __init__(self, typpe, value):
        self.type = typpe
        self.value = value


class Arg_Label:
    def __init__(self, name):
        self.name = name


class Arg_Type:
    def __init__(self, typpe):
        self.type = typpe


class Ins:
    expected_args = None

    def __init__(self, args):
        self.args = args

        #check if supplied correct arguments, count and instance
        if len(self.expected_args) != len(self.args):
            ErrorHandler.error_exit(
                    'wrong instruction argument count', ErrCode.BAD_XML)
        for i in range(0, len(self.args)):
            if not isinstance(self.args[i], self.expected_args[i]):
                ErrorHandler.error_exit(
                        'wrong instruction argument count', ErrCode.BAD_XML)

    def execute(self, program_context):
        pass

    @staticmethod
    def getDataFromSymbArg(arg, program_context):# either read from memory if var, or get literal value
        if isinstance(arg, Arg_Var):
            return program_context.readVariable(arg.frame, arg.name)
        elif isinstance(arg, Arg_Literal):
            return VariableData(arg.type, arg.value)
        else:
            ErrorHandler.error_exit(
                'bad instruction argument type', ErrCode.NONEXISTS_FRAME)  # TODO is this right?


class Ins_CREATEFRAME(Ins):
    expected_args = []
    def execute(self, program_context):
        program_context.createFrame()


class Ins_PUSHFRAME(Ins):
    expected_args = []
    def execute(self, program_context):
        program_context.pushFrame()


class Ins_POPFRAME(Ins):
    expected_args = []
    def execute(self, program_context):
        program_context.popFrame()


class Ins_BaseFun(Ins):
    def execute(self, program_context):
        pass

    def arg_type_error(self):
        ErrorHandler.error_exit(
            'instruction bad operand type', ErrCode.OPERAND_TYPE)


class Ins_BaseFun1(Ins_BaseFun):
    expected_args = [Arg_Var, Arg_Symb]
    def execute(self, program_context):
        var_data = Ins.getDataFromSymbArg(
            self.args[1], program_context)

        data_out = self.perform_calculation(var_data)

        program_context.writeVariable(
            self.args[0].frame, self.args[0].name, data_out)

    def check_types_match(self, var_data, type):
        if var_data.type != type:
            self.arg_type_error()

    def perform_calculation(self, var_data):
        pass


class Ins_BaseFun2(Ins_BaseFun):
    expected_args = [Arg_Var, Arg_Symb, Arg_Symb]
    def execute(self, program_context):
        var_data1 = Ins.getDataFromSymbArg(
            self.args[1], program_context)
        var_data2 = Ins.getDataFromSymbArg(
            self.args[2], program_context)

        data_out = self.perform_calculation(var_data1, var_data2)

        program_context.writeVariable(
            self.args[0].frame, self.args[0].name, data_out)

    def check_types_match(self, var_data1, var_data2, type1, type2):
        if var_data1.type != type1 or var_data2.type != type2:
            self.arg_type_error()

    def perform_calculation(self, var_data1, var_data2):
        pass


class Ins_BaseFun2Arithmetic(Ins_BaseFun2):
    def perform_calculation(self, var_data1, var_data2):
        self.check_types_match(var_data1, var_data2, VariableType.INT, VariableType.INT)
        value = self.operation(var_data1.value, var_data2.value)
        return VariableData(VariableType.INT, value)

    def operation(self, a, b):
        pass


class Ins_BaseFun2Log(Ins_BaseFun2):
    def perform_calculation(self, var_data1, var_data2):
        self.check_types_match(var_data1, var_data2,
                               VariableType.BOOL, VariableType.BOOL)
        value = self.operation(var_data1.value, var_data2.value)
        return VariableData(VariableType.BOOL, value)

    def operation(self, a, b):
        pass


class Ins_BaseFun2Rel(Ins_BaseFun2):  # TODO exetract comparison functionality to JUMPIFEQ
    def perform_calculation(self, var_data1, var_data2):
        if var_data1.type not in self.get_allowed_types() or var_data2.type not in self.get_allowed_types():
            self.arg_type_error()
        if var_data1.type != var_data2.type:
            if var_data1.type != VariableType.NIL and var_data2.type != VariableType.NIL:
                self.arg_type_error()
        value = self.operation(var_data1.value, var_data2.value)
        return VariableData(VariableType.BOOL, value)

    def get_allowed_types(self):
        return [VariableType.INT, VariableType.BOOL, VariableType.STRING]

    def operation(self, a, b):
        pass


class Ins_EQ(Ins_BaseFun2Rel):  # TODO allow for nil comparison, compare by type first
    def get_allowed_types(self):
        return [VariableType.NIL, VariableType.INT, VariableType.BOOL, VariableType.STRING]

    def operation(self, a, b):
        return a == b


class Ins_LT(Ins_BaseFun2Rel):
    def operation(self, a, b):
        return a < b


class Ins_GT(Ins_BaseFun2Rel):

    def operation(self, a, b):
        return a > b


class Ins_SETCHAR(Ins_BaseFun2):
    def execute(self, program_context):
        var_data1 = Ins.getDataFromSymbArg(
            self.args[1], program_context)
        var_data2 = Ins.getDataFromSymbArg(
            self.args[2], program_context)
        var_data0 = Ins.getDataFromSymbArg(
            self.args[0], program_context)

        self.check_types_match(var_data1, var_data2,
                               VariableType.INT, VariableType.STRING)
        if var_data0.type != VariableType.STRING:
            self.arg_type_error()

        data_out = var_data0
        index = var_data1.value
        if len(var_data2.value) == 0:
            ErrorHandler.error_exit(
                'SETCHAR empty char', ErrCode.BAD_STRING_MANIPULATION)
        char = var_data2.value[0]

        if index < 0 or index >= len(data_out.value):
            ErrorHandler.error_exit(
                'SETCHAR invalid index', ErrCode.BAD_STRING_MANIPULATION)

        prev_str = data_out.value
        data_out.value = prev_str[:index] + char + prev_str[index+1:]

        program_context.writeVariable(
            self.args[0].frame, self.args[0].name, data_out)


class Ins_STRI2INT(Ins_BaseFun2):
    def perform_calculation(self, var_data1, var_data2):
        self.check_types_match(var_data1, var_data2,
                               VariableType.STRING, VariableType.INT)
        value = self.operation(var_data1.value, var_data2.value)
        return VariableData(VariableType.INT, value)

    def operation(self, a, b):
        if b < 0 or b >= len(a):
            ErrorHandler.error_exit(
                'STRI2INT wrong index', ErrCode.BAD_STRING_MANIPULATION)
        return ord(a[b])


class Ins_CONCAT(Ins_BaseFun2):
    def perform_calculation(self, var_data1, var_data2):
        self.check_types_match(var_data1, var_data2,
                               VariableType.STRING, VariableType.STRING)
        value = self.operation(var_data1.value, var_data2.value)
        return VariableData(VariableType.STRING, value)

    def operation(self, a, b):
        return a + b


class Ins_GETCHAR(Ins_BaseFun2):
    def perform_calculation(self, var_data1, var_data2):
        self.check_types_match(var_data1, var_data2,
                               VariableType.STRING, VariableType.INT)
        value = self.operation(var_data1.value, var_data2.value)
        return VariableData(VariableType.STRING, value)

    def operation(self, a, b):
        if b < 0 or b >= len(a):
            ErrorHandler.error_exit(
                'GETCHAR wrong index', ErrCode.BAD_STRING_MANIPULATION)
        return a[b]


class Ins_STRLEN(Ins_BaseFun1):
    def perform_calculation(self, var_data):
        self.check_types_match(var_data, VariableType.STRING)
        value = self.operation(var_data.value)
        return VariableData(VariableType.INT, value)

    def operation(self, a):
        return len(a)


class Ins_NOT(Ins_BaseFun1):
    def perform_calculation(self, var_data):
        self.check_types_match(var_data, VariableType.BOOL)
        value = self.operation(var_data.value)
        return VariableData(VariableType.BOOL, value)

    def operation(self, a):
        return not a


class Ins_INT2CHAR(Ins_BaseFun1):
    def perform_calculation(self, var_data):
        self.check_types_match(var_data, VariableType.INT)
        value = self.operation(var_data.value)
        return VariableData(VariableType.STRING, value)

    def operation(self, a):
        try:
            return chr(a)
        except Exception:
            ErrorHandler.error_exit(
                'INT2CHAR failed', ErrCode.BAD_STRING_MANIPULATION)


class Ins_AND(Ins_BaseFun2Log):
    def operation(self, a, b):
        return a and b


class Ins_OR(Ins_BaseFun2Log):
    def operation(self, a, b):
        return a or b


class Ins_ADD(Ins_BaseFun2Arithmetic):
    def operation(self, a, b):
        return a + b


class Ins_MUL(Ins_BaseFun2Arithmetic):
    def operation(self, a, b):
        return a * b


class Ins_SUB(Ins_BaseFun2Arithmetic):
    def operation(self, a, b):
        return a - b


class Ins_IDIV(Ins_BaseFun2Arithmetic):
    def operation(self, a, b):
        if b == 0:
            ErrorHandler.error_exit(
                'IDIV division by 0', ErrCode.OPERAND_VALUE)
        return int(a / b)


class Ins_PUSHS(Ins):
    expected_args = [Arg_Symb]
    def execute(self, program_context):
        data = Ins.getDataFromSymbArg(self.args[0], program_context)
        program_context.pushStack(data)


class Ins_POPS(Ins):
    expected_args = [Arg_Var]
    def execute(self, program_context):
        data = program_context.popStack()
        program_context.writeVariable(
            self.args[0].frame, self.args[0].name, data)


def escape_string(x):
    arr = list(bytes(x, 'utf-8'))

    digits = range(48, 57+1)
    i = 0
    while i < len(arr)-4:
        if arr[i] == 92 and arr[i+1] in digits and arr[i+2] in digits and arr[i+3] in digits:
            num = int(bytes(arr[i+1:i+4]).decode('utf-8'))
            del arr[i:i+4]
            arr.insert(i, num)
        i += 1
    out = bytes(arr).decode('utf-8')
    return out


class Ins_JumpCon(Ins):
    expected_args = [Arg_Label, Arg_Symb, Arg_Symb]
    def arg_type_error(self):
        ErrorHandler.error_exit('instruction bad operand type', ErrCode.OPERAND_TYPE)

    def execute(self, program_context):
        data1 = Ins.getDataFromSymbArg(self.args[1], program_context)
        data2 = Ins.getDataFromSymbArg(self.args[2], program_context)
        if data1.type not in [VariableType.BOOL, VariableType.INT, VariableType.STRING, VariableType.NIL]:
            self.arg_type_error()
        if data1.type != data2.type:
            self.arg_type_error()
        if self.should_jump(data1, data2):
            program_context.jumpLabel(self.args[0].name)

    def should_jump(self, data1, data2):
        pass


class Ins_JUMPIFNEQ(Ins_JumpCon):
    def should_jump(self, data1, data2):
        return data1.value != data2.value


class Ins_JUMPIFEQ(Ins_JumpCon):  # TODO proper comparison types etc...
    def should_jump(self, data1, data2):
        return data1.value == data2.value


class Ins_WRITE(Ins):
    expected_args = [Arg_Symb]
    def execute(self, program_context):
        data = Ins.getDataFromSymbArg(self.args[0], program_context)
        if data.type == VariableType.STRING:
            value = escape_string(data.value)
        elif data.type == VariableType.BOOL:
            value = 'true' if data.value == True else 'false'
        elif data.type == VariableType.NIL:
            value = ''
        else:
            value = data.value
        print(value, file=sys.stdout, end='')


class Ins_DPRINT(Ins):
    expected_args = [Arg_Symb]
    def execute(self, program_context):
        data = Ins.getDataFromSymbArg(self.args[0], program_context)
        print(data.value, file=sys.stderr, end='')


class Ins_EXIT(Ins):
    expected_args = [Arg_Symb]
    def execute(self, program_context):
        var_data = Ins.getDataFromSymbArg(self.args[0], program_context)
        if var_data.type != VariableType.INT:
            ErrorHandler.error_exit(
                'exit wrong operand type', ErrCode.OPERAND_TYPE)
        if var_data.value not in range(0, 49+1):
            ErrorHandler.error_exit(
                'exit code not in range', ErrCode.OPERAND_VALUE)
        sys.exit(var_data.value)


class Ins_DEFVAR(Ins):
    expected_args = [Arg_Var]
    arg_count = 1

    def execute(self, program_context):
        program_context.declareVariable(self.args[0].frame, self.args[0].name)


class Ins_MOVE(Ins):
    expected_args = [Arg_Var, Arg_Symb]

    def execute(self, program_context):
        data = Ins.getDataFromSymbArg(self.args[1], program_context)
        program_context.writeVariable(
            self.args[0].frame, self.args[0].name, data)


class Ins_READ(Ins):
    expected_args = [Arg_Var, Arg_Type]
    
    def execute(self, program_context):
        input_str = program_context.input_stream.readline()
        input_str = input_str.split('\n')[0]

        typpe = self.args[1].type

        if (input_str == ''):  # TODO organize this
            if typpe == VariableType.STRING:
                data = VariableData(VariableType.STRING, '')
                program_context.writeVariable(
                    self.args[0].frame, self.args[0].name, data)
                return

            data = VariableData(VariableType.NIL, VariableType.NIL)
            program_context.writeVariable(
                self.args[0].frame, self.args[0].name, data)
            return

        typpe = self.args[1].type
        value = input_str

        if typpe == VariableType.BOOL:
            value = True if input_str.lower() == 'true' else False
        elif typpe == VariableType.INT:
            try:
                value = int(input_str)
            except Exception:
                value = 'nil'
                typpe = VariableType.NIL

        data = VariableData(typpe, value)
        program_context.writeVariable(
            self.args[0].frame, self.args[0].name, data)


class Ins_TYPE(Ins):
    expected_args = [Arg_Var, Arg_Symb]
    def execute(self, program_context):
        arg = self.args[1]
        type_str = None
        if isinstance(arg, Arg_Var):
            type_str = program_context.peekVarType(arg.frame, arg.name).value
        elif isinstance(arg, Arg_Literal):
            type_str = arg.type.value
        else:
            # TODO is this right?
            ErrorHandler.error_exit('TYPE wrong arg', ErrCode.NONEXISTS_FRAME)

        data = VariableData(VariableType.STRING, type_str)
        program_context.writeVariable(
            self.args[0].frame, self.args[0].name, data)


class Ins_LABEL(Ins):
    expected_args = [Arg_Label]
    def __init__(self, args):
        super().__init__(args)
        self.declared = False

    def execute(self, program_context):
        if self.declared == True:
            return
        program_context.declareLabel(self.args[0].name)
        self.declared = True


class Ins_JUMP(Ins):
    expected_args = [Arg_Label]
    def execute(self, program_context):
        program_context.jumpLabel(self.args[0].name)


class Ins_CALL(Ins):
    expected_args = [Arg_Label]
    def execute(self, program_context):
        program_context.callLabel(self.args[0].name)


class Ins_RETURN(Ins):
    expected_args = []
    def execute(self, program_context):
        program_context.returnLabel()


class InstructionFactory:

    @staticmethod
    def parseArg(arg):
        if arg.typename == 'var':
            split = arg.textval.split('@')
            frame = split[0]
            name = split[1]
            return Arg_Var(name, frame)
        elif arg.typename == 'int':
            try:
                val = int(arg.textval)
                return Arg_Literal(VariableType.INT, val)
            except Exception:
                ErrorHandler.error_exit('arg int bad value', ErrCode.BAD_XML)
        elif arg.typename == 'string':
            val = arg.textval
            if val == None:
                val = ''
            return Arg_Literal(VariableType.STRING, val)
        elif arg.typename == 'bool':
            val = None
            if arg.textval == 'true':
                val = True
            elif arg.textval == 'false':
                val = False
            else:
                ErrorHandler.error_exit('arg bool bad value', ErrCode.BAD_XML)
            return Arg_Literal(VariableType.BOOL, val)
        elif arg.typename == 'label':
            name = arg.textval
            return Arg_Label(name)
        elif arg.typename == 'nil':
            return Arg_Literal(VariableType.NIL, 'nil')
        elif arg.typename == 'type':
            if arg.textval == 'int':
                return Arg_Type(VariableType.INT)
            elif arg.textval == 'string':
                return Arg_Type(VariableType.STRING)
            elif arg.textval == 'nil':
                return Arg_Type(VariableType.NIL)
            elif arg.textval == 'bool':
                return Arg_Type(VariableType.BOOL)
            else:
                ErrorHandler.error_exit('arg type bad value', ErrCode.BAD_XML)

        ErrorHandler.error_exit('arg bad type', ErrCode.BAD_XML)

    @staticmethod
    def create_instruction(opcode, args):  # add args to constructor
        args = list(map(InstructionFactory.parseArg, args))
        ins_class_dict = {
            "MOVE": Ins_MOVE,
            "DEFVAR": Ins_DEFVAR,
            "WRITE": Ins_WRITE,
            "TYPE": Ins_TYPE,
            "EXIT": Ins_EXIT,
            "DPRINT": Ins_DPRINT,
            "READ": Ins_READ,
            "LABEL": Ins_LABEL,
            "JUMP": Ins_JUMP,
            "CALL": Ins_CALL,
            "RETURN": Ins_RETURN,
            "PUSHS": Ins_PUSHS,
            "POPS": Ins_POPS,
            "INT2CHAR": Ins_INT2CHAR,
            "ADD": Ins_ADD,
            "MUL": Ins_MUL,
            "AND": Ins_AND,
            "OR": Ins_OR,
            "SUB": Ins_SUB,
            "IDIV": Ins_IDIV,
            "STRLEN": Ins_STRLEN,
            "JUMPIFEQ": Ins_JUMPIFEQ,
            "JUMPIFNEQ": Ins_JUMPIFNEQ,
            "CREATEFRAME": Ins_CREATEFRAME,
            "PUSHFRAME": Ins_PUSHFRAME,
            "POPFRAME": Ins_POPFRAME,
            "CONCAT": Ins_CONCAT,
            "STRI2INT": Ins_STRI2INT,
            "GETCHAR": Ins_GETCHAR,
            "EQ": Ins_EQ,
            "LT": Ins_LT,
            "GT": Ins_GT,
            "NOT": Ins_NOT,
            "SETCHAR": Ins_SETCHAR,
        }

        if opcode not in ins_class_dict.keys():
            ErrorHandler.error_exit(
                'unknown opcode [{}]'.format(opcode), ErrCode.BAD_XML)

        return ins_class_dict[opcode](args)


class CustomParser(argparse.ArgumentParser):
    def print_help(self, file=None):
        print("IPPCode23 interpret")
        print("run with:")
        print("  python3 interpret.py ARGS")
        print("  ARGS:")
        print("    --help prints this message")
        print("    --source=SOURCE IPPCode23 source file")
        print("    --input=INPUT input file to read from")
        print("    by default INPUT = stdin and SOURCE = stdin")
        print("    so atleast one must be specified")


def main():
    # Parse arguments
    parser = CustomParser()

    parser.add_argument('--source')
    parser.add_argument('--input')

    args = parser.parse_args()

    source_file_path = args.source
    input_file_path = args.input

    if input_file_path == None and source_file_path == None:
        ErrorHandler.error_exit(
            "specify either --source or --input", ErrCode.CMD_ARGS)

    input_file = sys.stdin

    # if path specified open file else stdin
    if input_file_path != None:
        try:
            input_file = open(input_file_path)
        except Exception:
            ErrorHandler.error_exit(
                'could not open a file [{}]'.format(input_file_path), ErrCode.OPEN_INPUT_FILE)

    if source_file_path == None:
        source_file_path = sys.stdin

    try:
        tree = ET.parse(source_file_path)
    except Exception:
        ErrorHandler.error_exit('could not parse xml', ErrCode.FORMAT_XML)

    root = tree.getroot()

    instructions = []
    # go through xml instruction and instantate instruction objects
    for ins_obj in root:
        if ins_obj.tag != 'instruction':
            ErrorHandler.error_exit('bad instruction tag', ErrCode.BAD_XML)

        total_args = len(ins_obj)
        ins_args = [None for x in range(total_args)]

        for arg_obj in ins_obj:
            tag = arg_obj.tag.strip()
            if re.match('^arg[1-3]$', tag) == None:
                ErrorHandler.error_exit(
                    'wrong arg tag regex [{}]'.format(tag), ErrCode.BAD_XML)
            arg_index = int(tag[3:])-1
            if arg_index < 0 or arg_index >= total_args:
                ErrorHandler.error_exit(
                    'wrong arg index [{}]'.format(arg_index), ErrCode.BAD_XML)
            if 'type' not in arg_obj.attrib.keys():
                ErrorHandler.error_exit('arg missing type', ErrCode.BAD_XML)
            arg_type = arg_obj.attrib['type']
            arg_val = '' if arg_obj.text == None else arg_obj.text.strip()
            arg = ArgumentXML(arg_type, arg_val)
            ins_args[arg_index] = arg

        for x in ins_args:
            if x == None:
                ErrorHandler.error_exit('missing arg', ErrCode.BAD_XML)

        if 'opcode' not in ins_obj.attrib:
            ErrorHandler.error_exit('missing opcode', ErrCode.BAD_XML)
        if 'order' not in ins_obj.attrib:
            ErrorHandler.error_exit('missing order', ErrCode.BAD_XML)

        opcode_str = ins_obj.attrib['opcode']
        order_str = ins_obj.attrib['order']

        opcode = opcode_str.upper()
        try:
            order = int(order_str)
        except Exception:
            ErrorHandler.error_exit(
                'could not parse order [{}]'.format(order_str), ErrCode.BAD_XML)

        ins = InstructionFactory.create_instruction(opcode, ins_args)
        instructions.append((ins, order))

    # if any instructions
    if len(instructions) > 0:

        instructions.sort(key=lambda x: x[1])

        if instructions[0][1] < 1:  # make sure list starts from 1 or over
            ErrorHandler.error_exit(
                'order needs to start from 1 or over', ErrCode.BAD_XML)

        for i in range(0, len(instructions)-1):  # search for duplicite order
            if instructions[i][1] == instructions[i+1][1]:
                ErrorHandler.error_exit('duplicit order', ErrCode.BAD_XML)

        instructions = list(map(lambda x: x[0], instructions))

        # --interpret instructions
        program_context = ProgramContext(input_file)

        # --first just labels
        while program_context.program_counter < len(instructions):
            ins = instructions[program_context.program_counter]
            if isinstance(ins, Ins_LABEL):
                ins.execute(program_context)
            program_context.program_counter += 1

        program_context.program_counter = 0
        instructions_executed = 0

        # --whole program
        while program_context.program_counter < len(instructions):
            ins = instructions[program_context.program_counter]
            ins.execute(program_context)
            program_context.program_counter += 1
            instructions_executed += 1

    if input_file != sys.stdin:
        input_file.close()


if __name__ == "__main__":
    main()
