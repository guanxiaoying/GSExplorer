#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
Copyright (c) 2019 Stanley Guan

 This work is licensed under the terms of the GPL3 license.
 For a copy, see <https://opensource.org/licenses/GPL-3.0>.
 Author: Stanley Guan
 2019/03/01
dependencies:
     cryptcoder
     os
   3rd Libs:
     xml
     json
     zipfile
'''
import os, time
from cryptcoder import AESEncryption, b2a_hex, a2b_hex
import xml.etree.ElementTree as ET
import zipfile
import json
import subprocess
import threading 
from multiprocessing import Process
 
import traceback

NOT_FOUND = 1
FOUND = 2
def RunCmd(cmd):
    return subprocess.call(cmd,shell=True)
class PrintLogger():
    def __init__(self, parent = None ):
        self.parent = parent
    def log( self, msg ):
        print(msg.encode('utf-8'))
class TagObject():
    def __init__(self, name, tags):
        self.name = name
        self.tags = tags
class LabeledList(object):
    '''
    a sorted list by name
    '''
    def __init__(self):
        self.children = []
    def insert(self, c_with_name, ops="" ):
        name = c_with_name.name
        bingo,idx, _ = self.find(name)
        if bingo == 0:
            if '/F' in ops:
                self.children[idx] = c_with_name
            else:
                raise Exception("Already exists:%s"%name)
        else:
            if bingo == 1:
                if idx + 1 == len(self.children):
                    self.children.append(c_with_name)
                else:
                    self.children.insert(idx+1, c_with_name) 
            else:
                self.children.insert(idx, c_with_name) 
            
    def remove(self, name ):
        bingo, idx, ob = self.find(name)
        if bingo == 0 and ob is not None:
            return self.children.pop(idx)
        return None
    def find(self, name ):
        minIdx = 0
        maxIdx = len(self.children) - 1
        if maxIdx >= minIdx:
            ob = self.children[minIdx]
            if name == ob.name:
                return (0, minIdx, ob)
            ob = self.children[maxIdx]
            if name == ob.name:
                return (0, maxIdx, ob)
                        
        idx = int((minIdx+maxIdx)/2)
        ob = None
        bingo = -1
        while maxIdx >= minIdx:
            idx = int((minIdx+maxIdx)/2)
            ob = self.children[idx]
            if name > ob.name:
                minIdx = idx+1
                bingo = 1
            elif name < ob.name:
                maxIdx = idx-1
                bingo = -1
            else:
                bingo = 0
                break
        return (bingo, idx, ob)
    def get(self, idx):
        if idx < self.len():
            return self.children[idx]
    def len(self):
        return len(self.children)
    def __del__(self):
        for c in self.children:
            del c
        self.children = None
class Folder(object):
    def __init__(self, label = "", name = "", nid = 0 ):
        self.label = label
        self.name = name 
        self.id = nid
        self.parent = None
        self.isFolder = True
        self.subs = LabeledList()
        self.total_subs = 0
        self.total_files = 0
        self.not_found_file_state = 0
        self.tags = ''
        self.size = 0
        self.isRepo = True
        self.id_counter = 1
        self.createTime = ''
    def getFullPath(self):
        if self.parent is None:
            #root directory of a disk
            if len(self.name )  == 1:
                #windows style
                return self.name + ":\\"
            elif self.name[1] != ':' and self.name[0] != '/':
                #linux style
                return "/" + self.name
            else:
                return self.name
        else:
            return os.path.join( self.parent.getFullPath(), self.name )
    def getDummyPath(self):
        if self.parent is None:
            return ''
        return "-%s%s"%(self.id, self.parent.getDummyPath())
    def addChild(self, fObj, ops=''):
        self.subs.insert(fObj, ops)
        fObj.parent = self
        if isinstance(fObj, File):
            self.changeTotal( 0, 1)
        else:
            self.changeTotal( 1 + fObj.total_subs, fObj.total_files)
        self.changeSize(self.size, self.size + fObj.size)
        if fObj.id <= 0:
            self.id_counter = self.id_counter + 1
            fObj.id = self.id_counter 
        else:
            if self.id_counter <= fObj.id:
                self.id_counter = fObj.id
        
    def findChild(self, name ):
        bingo, _, ob = self.subs.find(name)
        if bingo == 0:
            return ob
        return None
    def removeChild(self, name):
        fObj = self.subs.remove(name)
        fObj.parent = None
        if isinstance(fObj, File):
            self.changeTotal( 0, -1)
        else:
            self.changeTotal( -1 - fObj.total_subs, -fObj.total_files)
        self.changeSize( self.size, max( 0, self.size - fObj.size ) )
    def changeTotal(self, dif_sub, dif_file ):
        self.total_files = self.total_files + dif_file
        self.total_subs = self.total_subs + dif_sub
        if self.parent is not None:
            self.parent.changeTotal( dif_sub, dif_file )        
    def changeSize(self, oldsize, newsize ):
        s = self.size
        self.size = max( 0, self.size - oldsize + newsize )
        if self.parent is not None:
            self.parent.changeSize( s, self.size )
    def hasChild(self):
        return self.subs.len() > 0
    def count(self):
        return self.subs.len() 
    def setState(self, state):
        if state == NOT_FOUND:
            self.not_found_file_state = self.not_found_file_state + 1
        elif state == FOUND:
            self.not_found_file_state = self.not_found_file_state - 1
        if self.parent:
            self.parent.setState(state)    
    def __str__(self):
        labels = ["label", "name", "parent", "isFolder", "total_subs", "total_files", "not_found", "size", "create" ]
        values = ['"%s"'%b2a_hex(self.label.encode('utf-8')).decode(), 
                  '"%s"'%b2a_hex(self.name.encode('utf-8')).decode(), 
                  '"%s"'%b2a_hex(self.parent.getFullPath().encode('utf-8')).decode(),
                  '%s'%1,
                  '%d'%self.total_subs,
                  '%d'%self.total_files,
                  '%d'%self.not_found_file_state,
                  '%d'%self.size,
                  '"%s"'%b2a_hex(self.createTime.encode('utf-8')).decode()
                  ]
        str_json = "{"
        for i in range(len(labels)):
            str_json = str_json + '"%s":%s,'%(labels[i], values[i])
        str_json = str_json + '"subs":%d}'%(self.count())  
        return str_json
    def __del__(self):
        del self.subs
class File(object):
    def __init__(self, label = "", name = "", nid = 0 ):
        self.label = label
        self.name = name 
        self.id = nid
        self.parent = None
        self.isFolder = False
        self.size = 0
        self.not_found_file_state = 0
        self.tags = ''
        self.createTime = ''
        if not name:
            raise Exception('Name is needed')
        self.isRepo = True
    def getTagName(self):
        return '%s-%d'%(self.label, self.size)
    def getFullPath(self):
        if self.parent is None:
            return self.name
        return os.path.join( self.parent.getFullPath(), self.name )
    def getDummyPath(self):
        if self.parent is None:
            return self.label
        return "%s%s"%(self.label,self.parent.getDummyPath())
    def setState(self, state):
        if state == NOT_FOUND:
            self.not_found_file_state = 1
        elif state == FOUND:
            self.not_found_file_state = 0
        if self.parent:
            self.parent.setState(state)
    def changeSize(self, newsize ):
        if self.parent is not None:
            self.parent.changeSize( self.size, newsize )
        self.size = newsize 
    def __str__(self):
        labels = ["label", "name", "parent", "isFolder", "not_found", "tags", 'create','dummypath' ]
        values = ['"%s"'%b2a_hex(self.label.encode('utf-8')).decode(), 
                  '"%s"'%b2a_hex(self.name.encode('utf-8')).decode(), 
                  '"%s"'%b2a_hex(self.parent.getFullPath().encode('utf-8')).decode(),
                  '%s'%0,
                  '%d'%self.not_found_file_state,
                  '"%s"'%b2a_hex(self.tags.encode('utf-8')).decode(),
                  '"%s"'%b2a_hex(self.createTime.encode('utf-8')).decode(), 
                  '"%s"'%self.getDummyPath()
                  ]
        str_json = "{"
        for i in range(len(labels)):
            str_json = str_json + '"%s":%s,'%(labels[i], values[i])
        str_json = str_json + '"size":%s}'%( '%d'%self.size)  
        return str_json
class RepositoryFile():
    def __init__(self, file_path, coder=None, key = ""):
        self.__version = '2'
        self.path = file_path
        self.__coder = coder
        self.__key = key
        self.__sha1_of_org_file = None
    def __parseXmlNode(self, node, parent ):
        if node.tag == 'Folder':
            name = node.attrib['name']
            label = node.attrib['label']
            nid = int(node.attrib['id'])
            f = Folder( label, name, nid )
            for n in node:
                self.__parseXmlNode(n, f)
            if parent is not None:
                parent.addChild(f, '/F')
            else:
                return f
        elif node.tag == 'File':
            name = node.attrib['name']
            label = node.attrib['label']
            nid = int(node.attrib['id'])
            not_fund = 0
            if 'not_found' in node.attrib:
                not_fund = int(node.attrib['not_found'])
            f = File( label, name, nid )
            if 'size' in node.attrib:
                size = int(node.attrib['size'])
                f.size = size
            if 'create_at' in node.attrib:
                time = node.attrib['create_at']
                f.createTime = time
            parent.addChild(f, '/F')
            if not_fund > 0:
                f.setState(NOT_FOUND)
    def getTagFile(self):
        return self.path + ".tags"
    def readTagFile(self):
        TagList = LabeledList()
        if self.__key is None:
            return TagList
        filePath = self.getTagFile()
        if os.path.exists(filePath) == False:
            return TagList
        f = None
        
        try:
            f = open(filePath, 'r')
            for  line in f.readlines(): 
                str_content = line[0:-1]
                str_content = self.__coder.decrypt(str_content)
                str_c = str_content.split(':')
                tags = a2b_hex(str_c[1]).decode('utf-8')
                label = str_c[0]
                bingo,_,tagObj = TagList.find(label)
                if bingo != 0 or tagObj is None:
                    tagObj = TagObject(label, tags)
                tagObj.tags = tags
                TagList.insert(tagObj, '/F')
        finally:
            if f is not None:
                f.close()    
        return TagList
    def read(self):
        if self.__key is None:
            return None
        filePath = self.path
        if os.path.exists(filePath) == False:
            return
        f = None
        try:
            f = open(filePath, 'r')
            sha1_of_org_file = None
            checked_flag = False
            xml_contents = ''
            md5_str = None
            skip_version = 0
            for  line in f.readlines(): 
                if skip_version == 0:
                    skip_version = 1
                    continue
                elif sha1_of_org_file is None:
                    sha1_of_org_file = line[0:-1]
                elif checked_flag == False:
                    str_check = line[0:-1]
                    str_of_sha1= self.__coder.decrypt(str_check)
                    if str_of_sha1 != sha1_of_org_file:
                        raise Exception('Wrong password!')
                    checked_flag = True
                elif md5_str is None:
                    md5_str = line[0:-1]
                else:
                    str_content = line[0:-1]
                    str_content = self.__coder.decrypt(str_content)
                    md52 = AESEncryption.getMd5Str(str_content)
                    if md5_str == md52:
                        
                        try:
                             
                            str_content = str_content.replace('&',' ')
                            xml_contents = xml_contents + str_content.encode('utf-8').decode('utf-8')    
                        except:
                            str_con2 = str_content.encode('utf-8')
                            str_con3 = bytearray(len(str_con2))
                            for i in range(len(str_con2)):
                                if str_con2[i] >= 128 or str_con2[i]== '&':
                                    str_con3[i] = 0x30
                                else:
                                    str_con3[i] = str_con2[i]
                            print(str_con3.decode('utf-8')  )
                            xml_contents = xml_contents + str_con3.decode('utf-8')    
                        str_content = None
                    else:
                        raise Exception('Broken resposity')
                    str_content = None
                    md5_str = None
        finally:
            if f is not None:
                f.close()    
        self.__sha1_of_org_file = sha1_of_org_file
        node = ET.fromstring( xml_contents )
        return self.__parseXmlNode(node, None)
    def __createFileXml(self, file, xml_c):
        xml_c = xml_c + '<File name="%s" id="%d" label="%s" size="%d" not_found="%d" create_at="%s"/>\n'% \
                (file.name, file.id, file.label, file.size, file.not_found_file_state, file.createTime )
        return xml_c
    def __createFolderXml(self, folder=None, xml_c='' ):
        if folder is None:
            folder = self.__root_folder
        xml_c = xml_c + '<Folder name="%s" id="%d"  label="%s">\n'% \
            (folder.name, folder.id, folder.label)
        for c in folder.subs.children:
            if isinstance(c, Folder):
                xml_c = self.__createFolderXml( c, xml_c )
            elif isinstance( c, File):
                xml_c = self.__createFileXml( c, xml_c )
        xml_c = xml_c + '</Folder>\n'
        return xml_c
    def write(self, root_folder):
        if self.__key is None:
            return
        filePath = self.path
        filePath2 = self.path + '.bin'
        xml_contents = ''
        xml_contents = self.__createFolderXml( root_folder, xml_contents )
        sha1_of_org_file = AESEncryption.getSha1Str(xml_contents)
        if self.__sha1_of_org_file != sha1_of_org_file:
            f = None
            try:

                f = open(filePath, 'w')
                str_check = self.__coder.encrypt(sha1_of_org_file)
                f.write('%s\n'%self.__version)
                f.write('%s\n'%sha1_of_org_file)
                f.write('%s\n'%str_check)
                while len(xml_contents) >= 256:
                    x = xml_contents[0:256]
                    x1 = self.__coder.encrypt(x)
                    x2 = AESEncryption.getMd5Str(x)
                    f.write('%s\n'%x2)
                    f.write('%s\n'%x1)
                    xml_contents = xml_contents[256:]
                x = xml_contents 
                x1 = self.__coder.encrypt(x)
                x2 = AESEncryption.getMd5Str(x)
                f.write('%s\n'%x2)
                f.write('%s\n'%x1)
                f.close()   
                f = None
                zip_instance = zipfile.ZipFile( filePath2, 'w', zipfile.ZIP_DEFLATED )
                zip_instance.write( filePath )
                zip_instance.close()                
            finally:
                if f is not None:
                    f.close()       
            self.__sha1_of_org_file = sha1_of_org_file
    def writeTagFile(self, tagList):
        if self.__key is None:
            return
        filePath = self.getTagFile()
        f = None
        try:

            f = open(filePath, 'w')
            for tag in tagList.children:
                x1 = tag.name
                x2 = b2a_hex(tag.tags.encode('utf-8')).decode()
                x = '%s:%s'%(x1,x2)
                x  = self.__coder.encrypt(x)
                f.write('%s\n'%x)
        finally:
            if f is not None:
                f.close()       
class Repository(object):
    def __init__(self, disk = 'c', key = "", logger = None):
        self.__version= '2'
        self.__disk = disk or 'c'
        self.__disk = self.__disk[0:1].lower()
        self.__rsPath = os.path.join(self.__disk + ':\\', '.gse') 
        self.__root_folder = Folder(self.__disk,self.__disk)
        self.logger = logger or PrintLogger()
        self.isDirty = False
        self.tagList = LabeledList()
        if key:
            self.__key = AESEncryption.getSha1Str(key)
            self.__coder = AESEncryption(key)
            self.__sha1_of_org_file = None
            self.__rsPath2 = os.path.join(self.__rsPath , self.__key)
            self.repoFile = RepositoryFile(os.path.join(self.__rsPath, "%s.resposity"%self.__key), AESEncryption(key), self.__key )
 
            self.__checkEnv( )
            self.__readRepository()
        else:
            raise Exception('Need password')
        
    def __del__(self):
        try:
            if self.isDirty:
                self.flush()
        finally:
            if self.__root_folder:
                del self.__root_folder
    def __checkEnv(self ):
        if not os.path.exists(self.__rsPath):
            os.mkdir(self.__rsPath)
            RunCmd('attrib +H %s'%(self.__rsPath))
        if not os.path.exists(self.__rsPath2):
            os.mkdir(self.__rsPath2)
    def __readRepository(self):
        if self.__key is None:
            return
        filePath = os.path.join(self.__rsPath, "%s.resposity"%self.__key)
        if os.path.exists(filePath) == False:
            return
        v = 0
        f = None
        try:
            f = open(filePath, 'r')
            line = f.read(2)
            if len(line) == 0:
                return
            if line[0] == '2':
                v = 2
        finally:
            if f is not None:
                f.close()         
        try:
            if v == 2:
                __root = self.repoFile.read()
                if self.__root_folder.name != __root.name:
                    __root.name = self.__root_folder.name
                self.__root_folder = __root
        except Exception as e:
            if 'Broken' in e.args[0]:
                filePath2 = self.path + '.bin'
                zip_instance = zipfile.ZipFile( filePath2, 'r'  )
                file_list = zip_instance.namelist()  
                if len(file_list) > 0:
                    zip_instance.extract(file_list[0], self.__root_folder.getFullPath())
                    if v == 2:
                        __root = self.repoFile.read()
                        if self.__root_folder.name != __root.name:
                            __root.name = self.__root_folder.name
                        self.__root_folder = __root
            else:
                raise
        self.check()
        self.__writeRepository()
        self.tagList = self.repoFile.readTagFile()
    def checkFolder(self, parent, fObj, progress = None):
        num = 0
        for c in fObj.subs.children:
            if c is None:
                continue
            if isinstance(c, File):
                num = num + self.checkFile(fObj,c,progress)
            else:
                num = num + self.checkFolder(fObj,c,progress)
            if not  fObj.createTime or ( c.createTime and c.createTime > fObj.createTime ):
                fObj.createTime = c.createTime 
        if num == 0:
            parent.removeChild(fObj.name)
        return num            
    def checkFile(self, parent, fObj, progress = None):
        dummP = self.__getDummyFullPath(fObj)
        num = 0
        if os.path.exists(dummP):
            if fObj.not_found_file_state > 0:
                fObj.setState(FOUND)
            size = os.path.getsize(dummP)
            fObj.changeSize(size)
            if not fObj.createTime:
                fObj.createTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getctime( dummP )) ) 
            num = 1
        else:
            parent.removeChild(fObj.name)
        if progress:
            progress.step(fObj.name)
        return num
    def check(self, progress = None):
        for c in self.__root_folder.subs.children:
            if isinstance(c, File):
                self.checkFile(self.__root_folder,c, progress)
            else:
                self.checkFolder(self.__root_folder,c,progress)
    def __writeRepository(self):
        if self.__version == '1':
            self.repoFile1.write(self.__root_folder)
        else:
            self.repoFile.write(self.__root_folder) 
 
    def __getDummyFullPath(self, target ):
        dummyP = target.getDummyPath()
        dummyPFull = os.path.join( self.__rsPath2, dummyP )
        return dummyPFull        
    def getRepoRoot(self):
        return self.__rsPath2
    def flush(self):
        self.__writeRepository()
        self.isDirty = False
        self.repoFile.writeTagFile(self.tagList)
    def saveTags(self):
        self.repoFile.writeTagFile(self.tagList)
    def getChildO(self, folder_obj):
        data = []
        for c in folder_obj.subs.children:
            data.append(c)
        return data
    def getChildS(self, folder_path):
        f = self.getDir(folder_path)
        if f is not None:
            return self.getChildO(f)
        return []
    def getParent(self, folder_path):
        f = self.getDir(folder_path)
        if f is not None:
            return f.parent
        return None
    def getDir(self, folder_path):
        if not folder_path:
            return self.__root_folder
        folder_path = folder_path.lower()
        segs = os.path.split(folder_path)
        if segs[0] == folder_path:
            if not self.__disk in segs[0]:
                return None
            return self.__root_folder
        elif segs[1] == '':
            return self.getDir(segs[0])
        else:
            f = self.getDir(segs[0])
            if f is not None:
                fobj = f.findChild(segs[1])
                if fobj is not None and fobj.isFolder:
                    return fobj
            return None
    def getFile(self, file_path):
        if not file_path:
            return None
        folder_path = file_path.lower()
        segs = os.path.split(folder_path)
        if segs[0] == folder_path:
            return None
        elif segs[1] == '':
            return None
        else:
            f = self.getDir(segs[0])
            if f is not None:
                fobj = f.findChild(segs[1])
                if not fobj.isFolder:
                    return fobj
            return None
    def _collectAllFiles(self, rdir, data, limited ):
        for c in rdir.subs.children:
            if isinstance(c, Folder):
                self._collectAllFiles(c, data, limited)
            else:
                data.append(c)
            if len(data) > limited:
                return 
    def allFiles(self, path, limited):
        rdir = self.getDir(path)
        if rdir is not None:
            data = []
            self._collectAllFiles(rdir,data,limited)
            return data
        rfile = self.getFile(path)
        if rfile is not None:
            return [rfile]
        return []
    def _collectByTag(self, rdir, labels, data, limited ):
        for c in rdir.subs.children:
            if isinstance(c, Folder):
                self._collectByTag(c, labels, data, limited)
            else:
                if c.getTagName() in labels:
                    data.append(c)
            if len(data) > limited:
                return 
    def getByTag(self, tag, limited):
        labels = []
        for tagObj in self.tagList.children:
            if tag in tagObj.tags:
                labels.append(tagObj.name)
        rdir = self.__root_folder
        if rdir is not None:
            data = []
            self._collectByTag(rdir, labels, data,limited)
            return data
        return []        
    def _collectByName(self, rdir, name, data, limited ):
        for c in rdir.subs.children:
            if name in c.name:
                data.append(c)
            if isinstance(c, Folder):
                self._collectByName(c, name, data, limited)
            if len(data) > limited:
                return 
    def getByName(self, name, limited):
        rdir = self.__root_folder
        if rdir is not None:
            data = []
            self._collectByName(rdir, name, data,limited)
            return data
        return []  
    ####################################
    # methods make changes
    ####################################
    def __createDir(self, folder_path ):
        folder_path = folder_path.lower()
        segs = os.path.split(folder_path)
        try:
            if segs[0] == folder_path:
                if not self.__disk in segs[0]:
                    raise Exception('Must be in the current disk:%s'%self.__disk)
                return self.__root_folder
            elif segs[1] == '' or segs[1] == '.':
                return self.__createDir(segs[0])
            elif segs[1] == '..':
                segs = os.path.split(segs[0])
                return self.__createDir(segs[0])
            else:
                folder = self.__createDir( segs[0])
                fObj = folder.findChild(segs[1])
                if fObj is None:
                    label = AESEncryption.getSha1Str(segs[1])
                    fObj = Folder(label, segs[1], 0 )
                    folder.addChild(fObj, '/F')
                else:
                    if isinstance(fObj, File):
                        raise Exception('File with the same name:%s'%folder_path)
                return fObj
        except:
            raise Exception('File with the same name:%s'%folder_path)
    def __commitFile(self, file ):   
        filePath = self.__getDummyFullPath(file)
        fullpath = file.getFullPath()
        cmd = 'move /Y "%s" "%s"'%( fullpath, filePath )
        return RunCmd(cmd)
    def __checkoutFile(self, file ):   
        filePath = self.__getDummyFullPath(file)
        fullpath = file.getFullPath()
        segs = os.path.split(fullpath)
        os.makedirs(segs[0], exist_ok=True)
        cmd = 'move /Y "%s" "%s"'%( filePath, fullpath )
        return RunCmd(cmd)
    def __removeEmptyFolder(self, folder ):
        if folder.parent is None:
            return
        parent = folder.parent
        parent.removeChild(folder.name)
        del folder
        if parent.hasChild() == False:
            self.__removeEmptyFolder(parent)
    def commitFile(self, file_path):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None
        file_path = file_path.lower()
        segs = os.path.split(file_path)
        if segs[1] == '' or segs[1] == '.' or segs[1] == '..':
            return None
        parent = self.__createDir(segs[0])
        if parent is None:
            return None
        fObj = parent.findChild(segs[1])
        label = AESEncryption.getSha1Str(segs[1])
        if fObj is None:
            fObj = File(label, segs[1], 0 )
            parent.addChild(fObj, '/F')
        else:
            if isinstance(fObj, File):
                fObj.label = label
            else:
                raise Exception('Directory with the same name:%s'%file_path)
        size = os.path.getsize(file_path)
        fObj.changeSize(size)
        fObj.createTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getctime( file_path )) ) 
        
        msgs = ['SUCCESS', 'FAILED']
        
        res = self.__commitFile(fObj)
        if res != 0:
            #failed to move file
            parent.removeChild(fObj.name)
            fObj = None
            res = 1
        
        self.logger.log( '[%s]commit %s'%(msgs[res], file_path))
        self.isDirty = True
        return fObj
 
    def checkoutFile(self, file_path):
        if file_path is None:
            return None
        file_path = file_path.lower()
        segs = os.path.split(file_path)
        if segs[1] == '' or segs[1] == '.' or segs[1] == '..':
            return None
        fObj = self.getFile(file_path)
        if fObj is None:
            return None
        msgs = ['SUCCESS', 'FAILED']
        res = self.__checkoutFile(fObj)
        if res != 0:
            #failed to move file
            fObj = None
            res = 1
        else:
            parent = fObj.parent
            parent.removeChild(fObj.name)
            if parent.count() == 0:
                self.__removeEmptyFolder(parent)
        self.logger.log( '[%s]checkout %s'%(msgs[res], file_path))
        self.isDirty = True
        return fObj
    def clean(self, progress = None):
        if progress:
            progress.setProgress(self.__root_folder.total_files)        
        self.check(progress)
        self.isDirty = True
class StatusInfo():
    job_running = False
    command = None
    args = None
    progress = None
    running = False
    __repo = None
    logger = None
SI_FS = StatusInfo()
class RepositoryService(threading.Thread):
    def __init__(self, logger = None):
        threading.Thread.__init__(self) 
        global SI_FS
        SI_FS.running = False
        SI_FS.logger = logger or PrintLogger()
        SI_FS.__repo = None
    def changeRepo(self, disk ,key ):
        global SI_FS
        self.wait_idle()
        SI_FS.__repo = Repository(disk, key)
        SI_FS.__repo.logger = SI_FS.logger
    def __assert(self):
        global SI_FS
        if SI_FS.__repo is None:
            raise Exception('unknown repository')
    def wait_idle(self):
        global SI_FS
        while SI_FS.job_running:
            time.sleep(0.5)        
    def kill(self):
        global SI_FS
        self.wait_idle()
        SI_FS.running = False
    def run(self):
        global SI_FS 
 
        """Run Worker Thread."""
        SI_FS.running = True
        while SI_FS.running: 
            self.wait_idle()
            time.sleep(0.5) 
            if SI_FS.command is not None:
                print('run')
                try:
                    SI_FS.job_running = True
                    if SI_FS.command == 'clean':
                        self.__clean(self.progress)
                    elif SI_FS.command == 'commit':
                        if isinstance(SI_FS.args, str):
                            self.__commitFile(SI_FS.args, SI_FS.progress)
                        else:
                            self.__commitFiles(SI_FS.args, SI_FS.progress)
                    elif SI_FS.command == 'checkout':
                        if isinstance(SI_FS.args, str):
                            self.__checkoutFile(SI_FS.args, SI_FS.progress)
                        else:
                            self.__checkoutFiles(SI_FS.args, SI_FS.progress)
                    elif SI_FS.command == 'open':
                        self.__openFile(SI_FS.args, SI_FS.progress)
                    SI_FS.job_running = False
                    if SI_FS.progress:
                        SI_FS.progress.finish(  'finished')
                except:
                    SI_FS.job_running = False
                    SI_FS.logger.log(traceback.format_exc())
                    if SI_FS.progress:
                        SI_FS.progress.stop('stopped')
                finally:
                    SI_FS.command = None
                    SI_FS.args = None    
    #================================
    # syn
    #================================
    def getDir(self, path ):
        global SI_FS 
        self.__assert()
        if SI_FS.job_running :
            raise Exception('Job is running!')
        folder = SI_FS.__repo.getDir(path)
        if folder is not None:
            f = FObject(SI_FS.__repo.getRepoRoot())
            f.parse(str(folder))
        return None
    def getFile(self, path ):
        global SI_FS 
        self.__assert()
        if SI_FS.job_running :
            raise Exception('Job is running!')
        f = SI_FS.__repo.getFile(path)
        if f is not None:
            f = FObject(SI_FS.__repo.getRepoRoot())
            f.parse(str(f))
            
            #tags
            bingo,_,tagObj = SI_FS.__repo.tagList.find(f.getTagName())
            if bingo == 0 and tagObj is not None:
                f.tags = tagObj.tags
        return None
    def getChildren(self, path ):
        global SI_FS 
        self.__assert()
        if SI_FS.job_running :
            raise Exception('Job is running!')
        cs = SI_FS.__repo.getChildS(path)
        res = []
        for c in cs:
            f = FObject(SI_FS.__repo.getRepoRoot())
            f.parse(str(c))
            res.append(f)
        res2 = []
        for r in res:
            if r.isFolder:
                res2.append(r)
        for r in res:
            if not r.isFolder:
                #tags
                bingo, _, tagObj = SI_FS.__repo.tagList.find(r.getTagName())
                if bingo == 0 and tagObj is not None:
                    r.tags = tagObj.tags
                res2.append(r)            
        return res2
    def getAllFiles(self, path, limited = 100000 ):
        global SI_FS 
        self.__assert()
        if SI_FS.job_running :
            raise Exception('Job is running!')
        return SI_FS.__repo.allFiles(path, limited)
    def getByTag(self, tag, limited = 100000 ):
        global SI_FS 
        self.__assert()
        if SI_FS.job_running :
            raise Exception('Job is running!')
        cs = SI_FS.__repo.getByTag(tag, limited)
        res = []
        for c in cs:
            f = FObject(SI_FS.__repo.getRepoRoot())
            f.parse(str(c))
            res.append(f)
            #tags
            bingo, _, tagObj = SI_FS.__repo.tagList.find(f.getTagName())
            if bingo == 0 and tagObj is not None:
                f.tags = tagObj.tags
        return res
    def getByName(self, name, limited = 10000 ):
        global SI_FS 
        self.__assert()
        if SI_FS.job_running :
            raise Exception('Job is running!')
        cs = SI_FS.__repo.getByName(name, limited)
        res = []
        for c in cs:
            f = FObject(SI_FS.__repo.getRepoRoot())
            f.parse(str(c))
            res.append(f)
            #tags
            bingo, _, tagObj = SI_FS.__repo.tagList.find(f.getTagName())
            if bingo == 0 and tagObj is not None:
                f.tags = tagObj.tags
        return res
    def removeInvalidFolder(self, path ):
        global SI_FS 
        fObj = self.getDir(path)
        return SI_FS.__repo.checkFolder(fObj.parent, fObj)
    def removeInvalidFile(self, path):
        global SI_FS 
        fObj = self.getFile(path)
        return SI_FS.__repo.checkFile(fObj.parent, fObj)
    def updateTags(self, fObjects):
        global SI_FS 
        self.__assert()
        if SI_FS.job_running :
            raise Exception('Job is running!')        
        #tags
        for fObject in fObjects:
            bingo, _, tagObj  = SI_FS.__repo.tagList.find(fObject.getTagName())
            if bingo != 0 or tagObj is None:
                tagObj = TagObject(fObject.getTagName(), fObject.tags)
                SI_FS.__repo.tagList.insert(tagObj)
            else:
                tagObj.tags = fObject.tags
        SI_FS.__repo.saveTags()
    #================================
    # asyn
    #================================
    def setAsynCall(self, command ,args, progress ):
        global SI_FS 
        self.wait_idle()
        SI_FS.job_running = True
        SI_FS.command = command
        SI_FS.args = args
        SI_FS.progress = progress
        SI_FS.job_running = False
    def __commitFile(self, path, progress = None):
        global SI_FS 
        self.__assert()
        if progress:
            progress.setProgress(2)
        obj = SI_FS.__repo.commitFile(path)
        if progress:
            progress.step(path)
        SI_FS.__repo.flush()
        return 1 if obj is not None else 0
    def __checkoutFile(self, path, progress = None):
        global SI_FS 
        self.__assert()
        if progress:
            progress.setProgress(2)
        obj = SI_FS.__repo.checkoutFile(path)
        if progress:
            progress.step(path)
        SI_FS.__repo.flush()
        return 1 if obj is not None else 0
    def __commitFiles(self, files=[], progress = None):
        global SI_FS 
        self.__assert()
        job_vol = len(files) + 1
        num = 0
        if progress:
            progress.setProgress(job_vol)        
        for path in files:
            obj = SI_FS.__repo.commitFile(path)
            if obj is not None:
                num = num + 1
            if progress:
                progress.step( path)
        SI_FS.__repo.flush()
        num = num + 1
        return num
    def __checkoutFiles(self, files=[], progress = None):
        global SI_FS 
        self.__assert()
        job_vol = len(files) + 1
        num = 0
        if progress:
            progress.setProgress(job_vol)        
        for path in files:
            obj = SI_FS.__repo.checkoutFile(path)
            if obj is not None:
                num = num + 1
            if progress:
                progress.step(path)
        SI_FS.__repo.flush()
        num = num + 1
        return num
    def __clean(self, progress = None):
        global SI_FS 
        self.__assert()
        SI_FS.job_running = True
        SI_FS.logger.log('clean started')
        SI_FS.__repo.clean(progress)
        SI_FS.__repo.flush()
    def __openFile(self, filepath, progress = None):
        global SI_FS 
        self.__assert()
        SI_FS.job_running = True
        SI_FS.logger.log('open %s'%filepath)
        f = SI_FS.__repo.getFile(filepath)
        if f is not None:
            SI_FS.__repo.checkoutFile(filepath)
            p = Process( target = open_file, args = ( filepath, ))
            p.start()
def open_file(file):
    RunCmd('"%s"'%file)
class FObject():
    def __init__(self, repoRoot):
        self.label = ''
        self.name = ''
        self.parent = ''
        self.isFolder = 0
        self.not_found = 0
        self.size = 0
        self.total_subs = 0
        self.total_files = 0
        self.sub_count = 0
        self.tags = ''
        self.isChecked = False
        self.isRepo = True
        self.createTime = ''
        self.dummypath = None
        self.repoRoot = repoRoot
    def __fromBytes(self, bytestr):
        return a2b_hex(bytestr).decode('utf-8')
    def getTagName(self):
        return '%s-%d'%(self.label, self.size)
    def parse(self, json_str):
        obj = json.loads(json_str)
        if 'label' in obj:
            self.label = self.__fromBytes(obj['label'])
        if 'name' in obj:
            self.name = self.__fromBytes(obj['name'])
        if 'parent' in obj:
            self.parent = self.__fromBytes(obj['parent'])
        if 'isFolder' in obj:
            self.isFolder = int(obj['isFolder']) > 0
        if 'not_found' in obj:
            self.not_found = int(obj['not_found']) 
        if 'total_subs' in obj:
            self.total_subs = int(obj['total_subs'])          
        if 'total_files' in obj:
            self.total_files = int(obj['total_files'])       
        if 'size' in obj:
            self.size = int(obj['size'])           
        if 'subs' in obj:
            self.sub_count = int(obj['subs'])     
        if 'tags' in obj:
            self.tags = self.__fromBytes(obj['tags'])
        if 'create' in obj:
            self.createTime = self.__fromBytes(obj['create'])
        if 'dummypath' in obj:
            self.dummypath = obj['dummypath']
    def getFullPath(self):
        return os.path.join(self.parent, self.name)
    def getDummyPath(self):
        return os.path.join(self.repoRoot, self.dummypath)
