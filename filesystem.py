#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
Copyright (c) 2019 Stanley Guan

 This work is licensed under the terms of the GPL3 license.
 For a copy, see <https://opensource.org/licenses/GPL-3.0>.
 Author: Stanley Guan
 2019/03/01
'''
import os,sys
import time
import subprocess
import threading 
from multiprocessing import Process
 
def RunCmd(cmd):
    print(cmd)
    return subprocess.call(cmd, shell = True )
def open_file(file):
    RunCmd('explorer "%s"'%file)
class BasicModel():
    def __init__(self, name ):
        segs = os.path.split(name)
        while segs[0] != name:
            name = segs[0]
            if segs[1] == '' or segs[1] == '.' :
                segs = os.path.split(name)
            elif segs[1] == '..' :
                segs = os.path.split(name)      
                segs = os.path.split(name)       
            else:
                break     
        self.parent = None
        self.name = None
        if segs[1] == '':
            self.name = segs[0]
        else:
            self.name = segs[1]
            self.parent = segs[0]
        self.isChecked = False
        self.mark = 50
        self.comment = ""
        self.size = 0
        self.lastAccess = None
        self.lastModify = None
        self.createTime = None
        self.hasEncrypt = False
        self.checkOut = False
        self.repoModel = None
        self.isReadOnly = False
        self.isHidden = False
        self.isSystem = False
        self.isRepo = False
        self.isFolder = False
    def isShown(self):
        return not self.isHidden and not self.isSystem
    def getRawPath(self):
        return self.getFullPath()
    def getFullPath(self):
        if self.parent is None:
            return self.name
        return os.path.join( self.parent, self.name )
    def getAttr(self ):
        if self.exists():
            real = self.getRawPath()
            self.size = os.path.getsize(real)
            self.lastAccess = os.path.getatime( real )
            self.lastModify = os.path.getmtime( real )
            self.createTime = os.path.getctime( real )
 
    def exists(self):
        return os.path.exists( self.getRawPath())
    def getParent(self):
        return self.parent
    def isDir(self):
        return self.isFolder
    def isFile(self):
        return not self.isFolder
    def getLastAccess(self):
        if self.lastAccess:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.lastAccess) )
        return ""
    def getLastModify(self):
        if self.lastAccess:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.lastModify) )
        return ""
    def getCreateTime(self):
        if self.lastAccess:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.createTime) )
        return ""
    def getSize(self):
        return 0
    def isEncrypt(self):
        return self.repoModel is not None
    def isCheckOut(self):
        return self.checkOut
    def getName(self):
        return self.name
    
class FileModel(BasicModel):
    def __init__(self, name  ):
        BasicModel.__init__( self, name   )      
        self.isFolder = False
        if self.parent is None:
            raise Exception('Wrong path')
        self.getAttr()
    def create(self):
        f = open( self.getFullPath(), 'w')
        f.close()
    def getSize(self):
        return self.size
    def isRoot(self):
        return False
class DirModel(BasicModel):
    def __init__(self, path ):
        BasicModel.__init__( self, path  )
        self.subs = []
        self.files = []
        self.totalFile = 0
        self.totalSub = 0
        self.isFolder = True
        self.getAttr()
    def isRoot(self):
        return self.parent == None
    def __mkdir(self):
        if self.exists() == False:
            par = self.getParent()
            if par != None:
                par.__mkdir()
            os.mkdir( self.path.getFullPath() )
    def get_( self, filename ):
        for i in range( 0, len(self.files)):
            if self.files[i].name == filename:
                return self.files[i]
        return None
    def delete_( self, filename ):
        for i in range( 0, len(self.files )):
            if self.files[i].name == filename:
                self.files.remove( self.files[i])
                #todo: delete
    def create(self):        
        self.__mkdir()

    def sublist(self):
        return self.subs

    def filelist(self):
        return self.files

    def nSubs(self):
        return len(self.subs)

    def nAllSubs(self):
        #TODO:
        return len( self.totalSub )

    def nFiles(self):
        return len(self.files)

    def nAllFiles(self):
        #TODO:
        return self.totalFile

    def getSize(self):
        return self.size

    def GetFolders(self, showHidden = True, showSystem = True ):
        dirs = []
        for d in self.subs:
            if showHidden == False and d.isHidden == True:
                continue
            if showSystem == False and d.isSystem == True:
                continue
            dirs.append(d)
        return dirs
    def GetFiles(self, showHidden = True, showSystem = True ):
        files = []
        for d in self.files:
            if showHidden == False and d.isHidden == True:
                continue
            if showSystem == False and d.isSystem == True:
                continue
            files.append( d )
        return files
 
    def refreshContainer(self ):
        self.refreshed = True
        
        self.files = []
        self.subs = []
        self.size = 0
        if not os.path.exists(self.getFullPath()):
            return
        lists = os.listdir( self.getFullPath())
        for i in range(0, len(lists)):
            name = lists[i]
            try:
                name.encode('utf-8')
            except:
                name = name.encode(sys.getdefaultencoding()).decode('utf-8')
            path = os.path.join(self.getFullPath(), name)
            if os.path.isdir(path):
                mDir = DirModel( path  )
                self.subs.append(mDir)
                self.size += mDir.getSize()
                self.totalSub += 1 + mDir.totalSub
                self.totalFile += mDir.totalFile
            else:
                mFile = FileModel( path )
                self.files.append(mFile)
                self.size += mFile.getSize()
                self.totalFile += 1
    def getAllFiles(self, limited):
        if len(self.subs) == 0:
            self.refreshContainer()
        data = []
        for file in self.files:
            data.append(file)
        if len(data) > limited:
            return data
        for sdir in self.subs:
            self.__getSubsFile( sdir, data, limited )
        return data
    def __getSubsFile(self, sdir, data, limited ):
        if len(sdir.subs) == 0:
            sdir.refreshContainer()
        for file in sdir.files:
            data.append(file)
        if len(data) > limited:
            return data
        for ssdir in sdir.subs:
            sdir.__getSubsFile( ssdir, data, limited )       
            if len(data) > limited:
                return data 
    
class PrintLogger():
    def __init__(self, parent = None ):
        self.parent = parent
    def log( self, msg ):
        print(msg.encode('utf-8'))
class StatusInfo():
    job_running = False
    command = None
    args = None
    progress = None
    running = False
    __repo = None
    logger = None
SI = StatusInfo()
class FileSystemService(threading.Thread):
    def __init__(self, logger = None):
        threading.Thread.__init__(self) 
        global SI
        SI.running = False
        SI.logger = logger or PrintLogger()
        SI.__repo = None
    def changeRepo(self, disk ,key ):
        pass
    def __assert(self):
        pass
    def wait_idle(self):
        global SI
        while SI.job_running:
            time.sleep(0.5)     
    def kill(self):
        global SI
        self.wait_idle()
        SI.running = False
    def run(self):
        global SI 
 
        """Run Worker Thread."""
        SI.running = True
        while SI.running: 
            self.wait_idle()
            time.sleep(0.5) 
            if SI.command is not None:
                print('run')
                try:
                    SI.job_running = True
                    if SI.command == 'open':
                        p = Process( target = open_file, args = ( SI.args, ))
                        p.start()
                    SI.job_running = False
                    if SI.progress:
                        SI.progress.finish(  'finished')
                except:
                    SI.job_running = False
                    if SI.progress:
                        SI.progress.stop('stopped')
                finally:
                    SI.command = None
                    SI.args = None    
    #================================
    # syn
    #================================
    def getDir(self, path ):
        global SI 
        self.__assert()
        if SI.job_running :
            raise Exception('Job is running!')
        if os.path.exists(path):
            return DirModel(path)
        return None
    def getFile(self, path ):
        self.__assert()
        if SI.job_running :
            raise Exception('Job is running!')
        if os.path.exists(path):
            return FileModel(path)
        return None
    def getChildren(self, path ):
        self.__assert()
        if SI.job_running :
            raise Exception('Job is running!')
        cs = self.getDir(path)
        if cs is not None:
            cs.refreshContainer()
            return cs.subs + cs.files
        return []
    def getAllFiles(self, path, limited = 100000 ):
        self.__assert()
        if SI.job_running :
            raise Exception('Job is running!')
        cs = self.getDir(path)
        if cs is not None:
            return cs.getAllFiles(limited)
        file = self.getFile(path)
        if file is not None:
            return [file]
        return []
    def removeInvalidFolder(self, path ):
        global SI 
        files = self.getAllFiles(path, 2)
        if len(files) > 0:
            return
        RunCmd('rmdir /S /Q "%s"'%path)
        SI.logger.log('rmdir /S /Q "%s"'%path)
    #================================
    # asyn
    #================================
    def setAsynCall(self, command ,args, progress ):
        global SI 
        self.wait_idle()
        SI.job_running = True
        SI.command = command
        SI.args = args
        SI.progress = progress 
        SI.job_running = False