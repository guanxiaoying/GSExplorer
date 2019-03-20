#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
Copyright (c) 2019 Stanley Guan

 This work is licensed under the terms of the GPL3 license.
 For a copy, see <https://opensource.org/licenses/GPL-3.0>.
 Author: Stanley Guan
 2019/03/01
'''
import hashlib
from binascii import b2a_hex, a2b_hex
from Crypto.Cipher import AES
import struct

class AESEncryption():
    '''
       AES.MODE_CBC
       encrypt or decrypt a string to a string
    '''
    def __init__(self, password):
        if password:
            if isinstance(password, str):
                password = password.encode('utf-8')
            self.mode = AES.MODE_CBC
            ret = AESEncryption.getMd5Str(password)
            self.key = ret[:16].encode('utf-8')
            self.iv_param = ret[16:].encode('utf-8')
        else:
            self.key = None
            self.iv_param = None
    @staticmethod
    def getMd5Str(str_param ):
        str_param = str_param or ''
        if isinstance(str_param, str):
            str_param = str_param.encode('utf-8')
        hash1 = hashlib.md5()
        hash1.update(str_param)
        ret = hash1.hexdigest()    
        return ret
    @staticmethod
    def getSha1Str(str_param ):
        str_param = str_param or ''
        if isinstance(str_param, str):
            str_param = str_param.encode('utf-8')
        hash1 = hashlib.new('sha1')
        hash1.update(str_param)
        ret = hash1.hexdigest()    
        return ret
    def __datalen(self, data):
        lenstr = a2b_hex(data[0:8])
        return (struct.unpack("i", lenstr)[0])
    def encrypt(self, str_param):
        '''
        return string
        '''
        if self.key is None or not str_param:
            return str_param
        length = 16
        if isinstance(str_param, str):
            data = str_param.encode('utf-8')
        else:
            data = str_param
        count = len(data)
        if(count % length != 0) :
            add = length - (count % length)
            data = data + (b'\0' * add)
        else:
            add = 0
        cryptor = AES.new(self.key, self.mode, self.iv_param)
        res = b2a_hex(struct.pack("i", count ) ) + b2a_hex(cryptor.encrypt(data))
        return res.decode('utf-8')
    def decrypt(self, str_param ):
        '''
        return string
        '''
        if self.key is None or not str_param:
            return str_param
        if isinstance(str_param, str):
            data = str_param.encode('utf-8')
        lengh = self.__datalen(data)
        cryptor = AES.new(self.key, self.mode, self.iv_param)
        data2 = a2b_hex(data[8:])
        res = cryptor.decrypt(data2)
        if (lengh > 0) and (lengh < len(res)):
            res = res[0:lengh]
        return res.decode('utf-8')

       
