# -*- coding: utf-8 -*-
import re

from ..util import FunctionMaker, PEP8FunctionName, PEP8ArgName
from ..parser import CFunctionPrototype
from .. import config

from .c_to_ctypes_map import c_to_ctypes_map
from .decorator import add_keywords, catch_error
from .types import TaskHandle

DAQlib, DAQlib_variadic = config.get_lib()

class ParsedProperty(object):
    """ Cached property calculated by the parse method """
    def __init__(self, name):
        self._name = name

    def __get__(self, obj, type=None):
        if obj is not None:
            out = getattr(obj, '_'+self._name, None)
            if out is None:
                obj.parse()
                out = getattr(obj, '_'+self._name, None)
            return out


argsplit = re.compile(', |,') # Almost everywhere there is a space after the comma

class NativeFunctionMaker(FunctionMaker):
    _all = []

    arg_names = ParsedProperty("arg_names")
    arg_ctypes = ParsedProperty("arg_ctypes")

    is_variadic = False
    _native_function = None
   
    def parse(self):
        arg_names = []
        arg_ctypes = []
        for arg in argsplit.split(self.arg_string): 
            for (reg_expr, new_type, group_nb) in c_to_ctypes_map:
                reg_expr_result = reg_expr.search(arg)
                if reg_expr_result is not None:
                    if new_type=="variadic":
                        arg_ctypes.append(new_type)
                        arg_names.append("*args")
                        self.is_variadic = True
                        break
                    arg_ctypes.append(new_type)
                    arg_names.append(reg_expr_result.group(group_nb))
                    break # break the for loop  
        self._arg_names = arg_names  
        self._arg_ctypes = arg_ctypes

    def _create_function(self):
        if self.is_variadic:
            return self._create_variadic_function()
        name = self.name
        arg_list = self.arg_ctypes
        arg_name = self.arg_names
        # Fetch C function and apply argument checks
        cfunc = getattr(DAQlib, name, None)
        if cfunc is None:
            warnings.warn('Unable to load {0}'.format(name))
            return
        if config.NIDAQmxBase and 'Base' in name :
            name = name[:5]+name[9:]  
        setattr(cfunc, 'argtypes', arg_list)
        # Create error-raising wrapper for C function and add to module's dict
        func = add_keywords(arg_name)(catch_error(cfunc, name, arg_list, arg_name))
        func.__name__ = name
        func.__doc__ = '%s(%s) -> error.' % (name, ', '.join(arg_name))
        return func
    
    def _create_variadic_function(self):
        name = self.name
        arg_list = self.arg_ctypes
        arg_name = self.arg_names
        cfunc = getattr(DAQlib_variadic, name)
        if config.NIDAQmxBase and 'Base' in name :
            name = name[:5]+name[9:]    
        func = add_keywords(arg_name)(catch_error(cfunc, name, arg_list, arg_name))
        func.__name__ = name
        func.__doc__ = '%s(%s) -> error.' % (name, ', '.join(arg_name))
        return func

    @property
    def native_function(self):
        if self._native_function is None:
            self._native_function = self._create_function()
        return self._native_function

    @property
    def pep8_arg_names(self):
        return [PEP8ArgName(elm).pep8_name for elm in self.arg_names]

    @property
    def pep8_native_function(self):
        func = add_keywords(self.pep8_arg_names)(self.native_function)
        func.__name__ = self.pep8_name
        func.__doc__ = 'Function {self.pep8_name}({argnames})\n C function is {self.name}'.format(self=self, argnames=', '.join(self.pep8_arg_names))
        func._maker = self
        return func
        

    @property
    def is_task_function(self):
        if self.name in  ['DAQmxClearTask']:
            return False
        return self.arg_ctypes and self.arg_ctypes[0] is TaskHandle and 'task' in self.arg_names[0]


    def __repr__(self):
        return "{self.name}({arg_names})".format(self=self, arg_names = ', '.join(self.arg_names))

for elm in CFunctionPrototype.get_all():
    NativeFunctionMaker(elm)   

