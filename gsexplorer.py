#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
Copyright (c) 2019 Stanley Guan

 This work is licensed under the terms of the GPL3 license.
 For a copy, see <https://opensource.org/licenses/GPL-3.0>.
 Author: Stanley Guan
 2019/03/01
'''
import os
import wx
import wx.dataview as dv
from repository import RepositoryService 
from filesystem import DirModel,  FileSystemService, RunCmd
import traceback
import multiprocessing
OK = 0
SHOW_OPT = 1
FAILED = -1

class PrintLogger():
    def __init__(self, parent = None ):
        self.parent = parent
    def log( self, msg ):
        print(msg.encode('utf-8'))
class FSModel( ):
    '''
    implementation of all actions of files
    '''
    def __init__(self, repositories):
        self.drivers = []
        self.password = None #str
        self.currDriver = None #str
        self.currentDir = None #DirModel
        self.repositories = repositories#Resposity
        self.data = []
        self.__collect_all_driver()
    def __collect_all_driver(self):
        '''
        collect all valid drivers
        '''
        for i in range(65,91):
            vol = chr(i) + ':' + '\\'
            vol = u'%s'%vol
            if os.path.isdir(vol):
                self.drivers.append( vol[0:1].lower() )
    def Run(self):
        '''
        start all repository service threads
        '''
        for rep in self.repositories:
            rep.start()
    def Stop(self):
        '''
        stop all repository service threads
        '''
        for rep in self.repositories:
            rep.kill()
    def getData(self, refreshFlag = True ):
        '''
        get all data of views from each  repository service 
        '''
        if refreshFlag:
            data = []
            for repo in  self.repositories :
                data.append(repo.getChildren(self.currentDir))
            fsList = data[0]
            encodedList = data[1]
            for en in encodedList:
                for d in fsList:
                    if d.getName().lower() == en.name:
                        d.repoModel = en
                        break
            self.data = data
        return self.data
    def setCurrentDir( self, str_dirObj = None):
        '''
        change CurrentDir of views
        '''
        self.currentDir = str_dirObj 
    def __findTarget(self, name, idx = -1):
        '''
        find Object by name 
        idx = 0: left view
        idx = 1: right view
        idx = -1: both
        '''
        if idx >= 0 and idx < len(self.data):
            for fObj in self.data[idx]:
                if fObj.name == name:
                    return fObj        
        else:    
            for d in self.data:
                for fObj in d:
                    if fObj.name == name:
                        return fObj
        return None
    def setCurrentDriver(self, newDriver, password ):
        '''
        change disk
        '''
        newDriver = newDriver.lower()
        if newDriver in self.drivers:
            for repo in  self.repositories :
                repo.changeRepo ( self.currDriver, password )
                if self.currDriver != newDriver or self.currentDir is None:
                    self.currDriver = newDriver
                    self.currentDir =  self.currDriver + ":\\" 
    def activeItem(self, item_name, idx = -1):
        '''
        double click an item:
            when folder, go to the folder
            when file, open the file with explorer of windows. If in right view, decrypt firstly
                 TODO: check the extension?
        idx = 0: left view
        idx = 1: right view
        '''
        target = self.__findTarget(item_name, idx)
        if target is not None and target.isFolder:
            self.setCurrentDir( os.path.join(self.currentDir, target.name))
            return True
        else:
            if target.isRepo: #right view
                self.repositories[1].setAsynCall('open', target.getFullPath(), None )
            else:
                self.repositories[0].setAsynCall('open', target.getFullPath(), None )
            return False
    def gotoParent(self):
        '''
        go to parent folder
        '''
        path = self.currentDir
        segs = os.path.split(path)
        while segs[1] == '' and segs[0] != path:
            path = segs[0]
            segs = os.path.split(path)
        self.setCurrentDir(segs[0])
    def EncryptFile(self, targets, progress):
        '''
        encrypt all files selected or in the folders selected
        '''
        files = []
        # get all files
        for fObj in self.data[0]:
            for target in targets:
                if fObj.name == target.name:
                    if fObj.isFolder:
                        files2 = self.repositories[0].getAllFiles(fObj.getFullPath())
                        for f in files2:
                            files.append(f.getFullPath())
                    else:
                        files.append(fObj.getFullPath())        
                    break
        #register the action
        self.repositories[1].setAsynCall('commit', files, progress )
    def DecryptFile(self, targets, progress):
        '''
        encrypt all files selected or in the folders selected
        '''
        files = []
        # get all files
        for fObj in self.data[1]:
            for target in targets:
                if fObj.name == target.name:
                    if fObj.isFolder:
                        files2 = self.repositories[1].getAllFiles(fObj.getFullPath())
                        for f in files2:
                            files.append(f.getFullPath())
                    else:
                        files.append(fObj.getFullPath())        
                    break
        #register the action
        self.repositories[1].setAsynCall('checkout', files, progress )
    def EncryptFiles(self, progress):
        '''
        encrypt all files selected or in the folders selected
        '''
        files = []
        # get all files
        objs=[]
        for fObj in self.data[0]:
            if fObj.isChecked:
                if fObj.isFolder:
                    objs.append(fObj)
                else:
                    files.append(fObj.getFullPath())
        progress.setProgress(len(objs))
        for fObj in objs:
            progress.step(fObj.name)
            files2 = self.repositories[0].getAllFiles(fObj.getFullPath())
            for f in files2:
                files.append(f.getFullPath())
        progress.setProgress(100)
        #register the action
        self.repositories[1].setAsynCall('commit', files, progress )
        
    def DecryptFiles(self, progress):
        '''
        decrypt all files selected or in the folders selected
        '''
        files = []
        # get all files
        for fObj in self.data[1]:
            if fObj.isChecked:
                if fObj.isFolder:
                    files2 = self.repositories[1].getAllFiles(fObj.getFullPath())
                    for f in files2:
                        files.append(f.getFullPath())
                else:
                    files.append(fObj.getFullPath())
        #register the action
        self.repositories[1].setAsynCall('checkout', files, progress )
    def clearEmptyFolder(self):
        '''
        delete all empty folders in the left view
        '''
        repo = self.repositories[0]
        data = self.data[0]
        for folder in data:
            if folder.isFolder:
                try:
                    repo.removeInvalidFolder(folder.getFullPath())
                except:
                    pass
    def updateTags(self, fObjs):
        self.repositories[1].updateTags(fObjs)
    def destroy(self):
        '''
        exit
        '''
        for rep in self.repositories:
            rep.kill()
        for dlist in self.data:
            for fObj in dlist:
                del fObj
class Column1():
    '''
    Column configuration of data view
    '''
    def __init__(self, idstr, name = "", types ="text", editable = False, align = 0, width = -1, sortable = True ):
        self.col_id = idstr
        self.name = name or ""
        self.type = types or "text"
        self.editable = editable 
        self.align = align
        self.width = width
        self.sortable = sortable
class BasicViewDataModel(dv.DataViewIndexListModel):
    '''
     data model of repo view(right view) 
    '''
    def __init__(self ):
        dv.DataViewIndexListModel.__init__(self)
        self.data = []          #data shown in the view
        self.columns =[]
        self.lastRowData = None
        self.index = None
    def filterData(self, flist ):
        '''
          filter data to show
          and insert .. (go to parent) into the first One
        '''
        data = []
        for d in flist:
            data.append( d )
        self.data = data
    def RefreshData(self,data):
        '''
        refresh gui
        '''
        self.filterData(data)
        self.Reset( len(self.data) )        
    def GetItemTarget( self, item ):
        '''
        get Object from an item in the data view
        '''
        value = self.GetValue(item,1)
        if value.Text == '..':
            return (0, None)
        idx = 0
        for d in self.data:
            if d is not None and d.name == value.Text:
                return (idx, d)
            idx = idx + 1
        return (-1, None )
    def GetColumnCount(self):
        '''
        get count of columns
        '''
        return len(self.columns)
    def GetCount(self):
        '''
        get count in the list
        '''
        return len(self.data)
    def getSizeStr( self, num ):
        '''
        get the string represent size
        '''
        if num < 1024:
            return ("%d"% num) + " B"
        elif num < 1024 * 1024:
            return ("%.2f"% (int(num*100/1024)/100.0)) + " KB"
        elif num < 1024 * 1024 * 1024:
            return ("%.2f"% (int(num*100/1024/1024)/100.0)) + " MB"
        else:
            return ("%.2f"% (int(num*100/1024/1024/1024)/100.0)) + " GB"
    def convertTarget( self, target ):
        '''
        convert an Object(DirModel, FileModel) to an Item in dataview
        '''
        row = [""]* self.GetColumnCount()
        return row
    def GetValueByRow(self, row, col):
        '''
        get value of the grid indicated by row and col
          called by gui
        '''
        if self.lastRowData is not None and self.index is not None and self.index[0] == row and self.index[1] == col - 1:
            self.index = (row, col)
            if col >= 0 and col < len(self.lastRowData):
                return self.lastRowData[col]
            else:
                return None
        else:
            self.index = (row, col)
            target = None
            if row >= 0 and row < self.GetCount():
                target = self.data[row]
            self.lastRowData = self.convertTarget( target )
            if col >= 0 and col < len(self.lastRowData):
                return self.lastRowData[col]
        return None
    def SetValueByRow(self,variant, row, col):
        '''
        set value of the grid indicated by row and col
         not implemented
        '''
        if col == 0:
            if row >= 0 and row < self.GetCount():
                target = self.data[row]       
                target.isChecked = variant 
        return True    
class ResposityDataModel(BasicViewDataModel):
    '''
     data model of repo view(right view) 
    '''
    def __init__(self ):
        super(ResposityDataModel, self).__init__()
        self.initialColumns()
        
    def initialColumns(self):
        '''
        create columns of data view
        '''
        #check box
        self.columns.append( Column1( 0, types="bool", width = 30, sortable = True, align = 1 )) # selection
        #name and icon
        self.columns.append( Column1( 1, types="icontext", name = u"Name",  width = 200, sortable = True )) # name and icon
        #total size
        self.columns.append( Column1( 2,  name = u"Size", editable = False, width = 100, sortable = False )) # name and icon
        #total sub folders
        self.columns.append( Column1( 3,  name = u"folders", editable = False, width = 50, sortable = False )) # name and icon
        #total files
        self.columns.append( Column1( 4,  name = u"files", editable = False, width = 50, sortable = False )) # name and icon
        #tags
        self.columns.append( Column1( 5,  name = u"Tag", editable = False, width = 100, sortable = False )) # name and icon
        #tags
        self.columns.append( Column1( 6,  name = u"Date", editable = False, width = 100, sortable = False )) # name and icon
    def filterData(self, flist ):
        '''
          filter data to show
          and insert .. (go to parent) into the first One
        '''
        data = []
        for d in flist:
            if d is None:
                continue
            data.append( d )
        if len(data) == 0 or data[0] is not None:
            data.insert(0, None)
        self.data = data
   
    def convertTarget( self, target ):
        '''
        convert an Object(DirModel, FileModel) to an Item in dataview
        '''
        row = [""]* self.GetColumnCount()
        if target is None:
            row[1] =  dv.DataViewIconText(text = '..'  , icon = wx.Icon('./res/disk.png'))
            row[0] = False
        elif target.isFolder:
            row[0] = target.isChecked
            row[1] =  dv.DataViewIconText(text = target.name , icon = wx.Icon('./res/folder.png'))
            #row[2] = target.label
            row[2] = self.getSizeStr(target.size)
            row[3] = '%d'%target.total_subs
            if target.not_found > 0:
                row[4] = '%d?%d'%(target.total_files, target.not_found)
            else:
                row[4] = '%d'%(target.total_files )
            row[6] = target.createTime
        else:
            row[0] = target.isChecked
            row[1] =  dv.DataViewIconText(text = target.name  , icon = wx.Icon('./res/disk.png'))
            #row[2] = target.label
            if target.not_found > 0:
                row[2] = '?'
            else:
                row[2] = self.getSizeStr(target.size)
            if target.tags:
                row[5] = target.tags
            row[6] = target.createTime
        return row
    
class DirDataModel(BasicViewDataModel):
    '''
     data model of folder view(left view) 
    '''
    def __init__(self):
        super(DirDataModel,self).__init__()
        self.initialColumns()
        
    def initialColumns(self):
        '''
        create columns of data view
        '''
        #check box
        self.columns.append( Column1( 0, types="bool", width = 30, sortable = True, align = 1 )) # selection
        self.columns.append( Column1( 1, types="icontext", name = u"Name",  width = 300, sortable = True )) # name and icon
        self.columns.append( Column1( 2, types="icontext", name=u"Encry.", width = 100, sortable = False )) # encryption flag
        self.columns.append( Column1( 3, name=u"Size", width = 80, sortable = True ))  # size of file
        self.columns.append( Column1( 4, name=u"Create date",width = 150, sortable = True )) # create date
        self.columns.append( Column1( 5, name=u"Update date",width = 150, sortable = True )) # update date    
        
    def filterData(self, flist ):
        '''
          filter data to show
          and insert .. (go to parent) into the first One
        '''
        data = []
        for d in flist:
            if d is None:
                continue
            if d.name == ".gse":
                continue
            data.append( d )
        if len(data) == 0 or data[0] is not None:
            data.insert(0, None)
        self.data = data
    
    def convertTarget( self, target ):
        '''
        convert an Object(DirModel, FileModel) to an Item in dataview
        '''
        row = [""]* self.GetColumnCount()
        if target == None:
            row[0] = False
            row[1] = dv.DataViewIconText( ".." )
            row[2] = dv.DataViewIconText(text = '' , icon = wx.Icon('./res/none.png'))
        else:
            if target.isChecked:
                row[0] = True
            else:
                row[0] = False
            name = target.name
            if name != None:
                pass
            else:
                name = ""
            if isinstance(target, DirModel):
                row[1] =  dv.DataViewIconText(text = target.name , icon = wx.Icon('./res/folder.png'))
            else:
                row[1] =  dv.DataViewIconText(text = target.name  , icon = wx.Icon('./res/disk.png'))
                row[3] =  self.getSizeStr( target.size )
            if target.isEncrypt():
                row[2] = dv.DataViewIconText(text = '' , icon = wx.Icon('./res/lock.png'))
            else:
                row[2] = dv.DataViewIconText(text = '' , icon = wx.Icon('./res/none.png'))
            row[4] = target.getCreateTime()
            row[5] = target.getLastModify()
        return row
class Explorer(wx.Frame):
    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(Explorer, self).__init__(*args, **kw)
        self.Maximize(True)
        self.initialed = False
        self.logger = self
        self.fsm = FSModel( (FileSystemService(self.logger),RepositoryService(self.logger)) )
        self.dm_datamodels =( DirDataModel( ) , ResposityDataModel( ) )
        self.currentJobThread = []
        self.views = []
        # create a menu bar
        self.makeMenuBar()
        self.makeToolBar()
        self.CreatePanel()
        # and a status bar
        self.CreateStatusBar()
        self.createContextMenu()
        self.SetStatusText("Welcome to Guan's secure explorer!")
        accelTbl = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_DELETE, self.delselmmi.GetId()),\
                    (wx.ACCEL_NORMAL, wx.WXK_BACK, self.gotoparentmmi.GetId()),\
                     (wx.ACCEL_CTRL, wx.WXK_RIGHT, self.encryptmmi.GetId()),\
                    (wx.ACCEL_CTRL, wx.WXK_CONTROL_Q, self.m_clear.GetId())])
        self.m_dirView.SetAcceleratorTable(accelTbl)
    def __isValidPath(self, path):
        return path != None and len(path) > 0 and os.path.exists(path)
    def makeToolBar(self):
        self.fileToolBar = self.CreateToolBar( wx.TB_HORIZONTAL, wx.ID_ANY )
        self.fileToolBar.SetBackgroundColour( wx.Colour( 255, 255, 255 ) )
        self.m_refresh = self.fileToolBar.AddTool( wx.ID_ANY, u"refresh", wx.Bitmap( u"res/refresh.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Goto Parent", u"Goto Parent", None )
        
        #sep
        self.fileToolBar.AddTool( wx.ID_ANY, u"", wx.Bitmap( u"res/none.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Goto Parent", u"Goto Parent", None )
        
        self.m_clear = self.fileToolBar.AddTool( wx.ID_ANY, u"clear empty folders", wx.Bitmap( u"res/clear.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Delete", u"Delete", None )
        self.m_encode = self.fileToolBar.AddTool( wx.ID_ANY, u"Encrypt", wx.Bitmap( u"res/lock2.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Encode", u"Encode", None )
        #sep
        self.fileToolBar.AddTool( wx.ID_ANY, u"", wx.Bitmap( u"res/none.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Goto Parent", u"Goto Parent", None )
        
        self.m_decode = self.fileToolBar.AddTool( wx.ID_ANY, u"Decrypt", wx.Bitmap( u"res/unlock2.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Decode", u"Decode", None )
        self.m_searcht = self.fileToolBar.AddTool( wx.ID_ANY, u"Search tag", wx.Bitmap( u"res/searcht.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Options", u"Options", None )
        self.m_searchn = self.fileToolBar.AddTool( wx.ID_ANY, u"Search name", wx.Bitmap( u"res/searchn.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"Options", u"Options", None )

        self.m_album = self.fileToolBar.AddTool( wx.ID_ANY, u"Album", wx.Bitmap( u"res/album.png", wx.BITMAP_TYPE_ANY ), wx.NullBitmap, wx.ITEM_NORMAL, u"ALBUM", u"ALBUM", None )
 
        self.fileToolBar.Realize()
        self.Bind( wx.EVT_TOOL, self.OnRefresh, id = self.m_refresh.GetId() )
        self.Bind( wx.EVT_TOOL, self.OnClearEmptyFolder, id = self.m_clear.GetId() )
        self.Bind( wx.EVT_TOOL, self.OnDecrypt, id = self.m_decode.GetId() )
        self.Bind( wx.EVT_TOOL, self.OnEncrypt, id = self.m_encode.GetId() )
        self.Bind( wx.EVT_TOOL, self.OnSearchTag, id = self.m_searcht.GetId() )
        self.Bind( wx.EVT_TOOL, self.OnSearchName, id = self.m_searchn.GetId() )
        self.Bind( wx.EVT_TOOL, self.OnShowAsAlbum, id = self.m_album.GetId() )
 
    def makeMenuBar(self):
        # Make a file menu with Hello and Exit items
        self.fileMenu = wx.Menu()
        self.selectDiskItem = wx.MenuItem( self.fileMenu, wx.ID_ANY, u"Select disk", u"Select a disk", wx.ITEM_NORMAL )
        self.fileMenu.Append(self.selectDiskItem)
        self.exitItem = self.fileMenu.Append(wx.ID_EXIT)

        # Now a help menu for the about item
        self.helpMenu = wx.Menu()
        #self.manualItem = wx.MenuItem( self.helpMenu, wx.ID_ANY, u"Help", u"Help", wx.ITEM_NORMAL )
        #self.manualItem = self.helpMenu.Append(self.manualItem)
        self.aboutItem = self.helpMenu.Append(wx.ID_ABOUT)
 
        self.menuBar = wx.MenuBar()
        self.menuBar.Append(self.fileMenu, "&File")
        self.menuBar.Append(self.helpMenu, "&Help")

        # Give the menu bar to the frame
        self.SetMenuBar(self.menuBar)
        self.menuBar.SetBackgroundColour( wx.Colour( 255, 255, 255 ) )
 
        self.Bind(wx.EVT_MENU, self.OnGoto, self.selectDiskItem)
        self.Bind(wx.EVT_MENU, self.OnExit,  self.exitItem)
        self.Bind(wx.EVT_MENU, self.OnAbout, self.aboutItem)
        #self.Bind(wx.EVT_MENU, self.OnHelp, self.manualItem)
        
    def _createResposity(self,idx):
        self.m_repositoryView = dv.DataViewCtrl(self.panel,
                                   style=wx.BORDER_THEME | dv.DV_MULTIPLE| wx.EXPAND
                                   )
        self.views.append(self.m_repositoryView)
        for col in self.dm_datamodels[idx].columns:
            mode = 0
            if col.editable:
                mode = mode | dv.DATAVIEW_CELL_EDITABLE
            if col.type == "bool":
                dvc = self.m_repositoryView.AppendToggleColumn( col.name, col.col_id, mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "date":
                dvc = self.m_repositoryView.AppendDateColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "prog":
                dvc = self.m_repositoryView.AppendProgressColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "bitmap":
                dvc = self.m_repositoryView.AppendBitmapColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "icontext":
                dvc = self.m_repositoryView.AppendIconTextColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            else:
                dvc = self.m_repositoryView.AppendTextColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            if col.width > 0:
                dvc.SetWidth(col.width)
        self.m_repositoryView.AssociateModel(self.dm_datamodels[idx] )
        self.Bind(dv.EVT_DATAVIEW_ITEM_CONTEXT_MENU, self.OnContextMenu2, self.m_repositoryView)
        self.Bind(dv.EVT_DATAVIEW_ITEM_ACTIVATED, self.OnItemActivated, self.m_repositoryView)
        self.Bind(dv.EVT_DATAVIEW_ITEM_VALUE_CHANGED, self.OnItemValueChanged2, self.m_repositoryView)
        
        boxSizer = wx.BoxSizer( wx.VERTICAL )
        boxSizer.Add( self.m_repositoryView, proportion=1, flag=wx.EXPAND | wx.ALL, border = 5 )
        return boxSizer
    def _createExplorer(self,idx):
        boxSizer = wx.BoxSizer( wx.VERTICAL )
        self.m_dirView = dv.DataViewCtrl(self.panel,
                                   style=wx.BORDER_THEME | dv.DV_MULTIPLE | wx.EXPAND
                                   )
        self.views.append(self.m_dirView)
        # Display a header above the grid
        for col in self.dm_datamodels[idx].columns:
            mode = 0
            if col.editable:
                mode = mode | dv.DATAVIEW_CELL_EDITABLE
            if col.type == "bool":
                dvc = self.m_dirView.AppendToggleColumn( col.name, col.col_id, mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "date":
                dvc = self.m_dirView.AppendDateColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "prog":
                dvc = self.m_dirView.AppendProgressColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "bitmap":
                dvc = self.m_dirView.AppendBitmapColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            elif col.type == "icontext":
                dvc = self.m_dirView.AppendIconTextColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            else:
                dvc = self.m_dirView.AppendTextColumn(col.name, col.col_id , mode = dv.DATAVIEW_CELL_ACTIVATABLE | mode )
            if col.width > 0:
                dvc.SetWidth(col.width)
 
        self.m_dirView.AssociateModel( self.dm_datamodels[idx] )
        self.Bind(dv.EVT_DATAVIEW_ITEM_CONTEXT_MENU, self.OnContextMenu1, self.m_dirView)
        self.Bind(dv.EVT_DATAVIEW_ITEM_ACTIVATED, self.OnItemActivated, self.m_dirView)
        self.Bind(dv.EVT_DATAVIEW_ITEM_VALUE_CHANGED, self.OnItemValueChanged1, self.m_dirView)
        boxSizer.Add( self.m_dirView, proportion=1, flag=wx.EXPAND | wx.ALL, border = 5 )
        return boxSizer  
    def createContextMenu(self):
        self.contextMenu1 = wx.Menu( )
 
        mmi = wx.MenuItem(self.contextMenu1, wx.WXK_SEPARATOR, ' ')
        self.contextMenu1.Append(mmi)        
        self.encryptmmi = wx.MenuItem(self.contextMenu1, wx.NewId(), 'Encrypt')
        self.contextMenu1.Append(self.encryptmmi)
        self.Bind(wx.EVT_MENU, self.OnEncryptCM, self.encryptmmi)
        mmi = wx.MenuItem(self.contextMenu1, wx.WXK_SEPARATOR, ' ')
        self.contextMenu1.Append(mmi)
        mmi = wx.MenuItem(self.contextMenu1, wx.NewId(), 'Open')
        self.contextMenu1.Append(mmi)
        self.Bind(wx.EVT_MENU, self.OnOpen, mmi)
        mmi = wx.MenuItem(self.contextMenu1, wx.NewId(), 'Rename')
        self.contextMenu1.Append(mmi)
        self.Bind(wx.EVT_MENU, self.OnRenameFile, mmi)
        mmi = wx.MenuItem(self.contextMenu1, wx.WXK_SEPARATOR, ' ')
        self.contextMenu1.Append(mmi)
        mmi = wx.MenuItem(self.contextMenu1, wx.NewId(), 'Delete')
        self.contextMenu1.Append(mmi)
        self.Bind(wx.EVT_MENU, self.OnDeleteFile, mmi)
        self.delselmmi = wx.MenuItem(self.contextMenu1, wx.NewId(), 'Delete all of selection')
        self.contextMenu1.Append(self.delselmmi)
        self.Bind(wx.EVT_MENU, self.OnDeleteFiles, self.delselmmi)
        self.gotoparentmmi = wx.MenuItem(self.contextMenu1, wx.NewId(), 'Goto parent')
        self.contextMenu1.Append(self.gotoparentmmi)
        self.Bind(wx.EVT_MENU, self.OnGotoParent, self.gotoparentmmi)
        
        self.contextMenu2 = wx.Menu( )
        mmi = wx.MenuItem(self.contextMenu2, wx.NewId(), 'Decrypt')
        self.contextMenu2.Append(mmi)
        self.Bind(wx.EVT_MENU, self.OnDecryptCM, mmi)

        self.contextMenu3 = wx.Menu( )
        mmi = wx.MenuItem(self.contextMenu3, wx.NewId(), 'Decrypt')
        self.contextMenu3.Append(mmi)
        self.Bind(wx.EVT_MENU, self.OnDecryptCM, mmi)
        mmi = wx.MenuItem(self.contextMenu3, wx.NewId(), 'Edit tags')
        self.contextMenu3.Append(mmi)
        self.Bind(wx.EVT_MENU, self.OnEditTags, mmi)
    def CreatePanel(self):
        self.panel = self
        self.panel.SetBackgroundColour('white')
        self.boxSizer = wx.BoxSizer( wx.VERTICAL )
        
        boxSizer = wx.BoxSizer( )
        boxSizer1 = self._createExplorer(0)
        boxSizer2 = self._createResposity(1)
        boxSizer.Add( boxSizer1, 1, wx.EXPAND, 5 )
        boxSizer.Add( boxSizer2, 1, wx.EXPAND, 5 )
        
        self.logger = wx.TextCtrl(self, size= wx.Size( -1, 150), style=wx.TE_MULTILINE )
        self.progress = wx.Gauge(self, range=20)
        self.information = wx.TextCtrl( self, wx.ID_ANY, u"idle", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.progress.SetBackgroundColour('white')
        self.information.SetBackgroundColour('white')
        self.boxSizer.Add( boxSizer, 2,  wx.EXPAND, 5 )
        self.boxSizer.Add( self.logger, 0, wx.ALL|wx.EXPAND, 5 )
        self.boxSizer.Add( self.progress, 0, wx.EXPAND, 0 )
        self.boxSizer.Add( self.information, 0, wx.EXPAND, 0 )
        self.panel.SetSizer(self.boxSizer, deleteOld=True)
        self.Layout()

    def log(self, msg ):
        self.logger.AppendText(msg+'\n')
    def clear(self):
        self.logger.SetValue('')
    def setProgress(self, count ):
        self.progress.SetRange(count)
        self.progress.SetValue(0)
        self.information.SetValue('Ready')
    def step(self, msg, steps = 1):
        va = self.progress.GetValue()
        count = self.progress.GetRange()
        if va < count - steps:
            va = va + steps
        self.progress.SetValue(va)
        self.information.SetValue(  '[%d/%d] %s'%( va, count, msg ))     
    def finish(self, msg ):
        self.progress.SetValue( self.progress.GetRange() )
        self.information.SetValue(msg)         
        self.refreshList(True)
    def stop(self, msg ):
        self.progress.SetValue( self.progress.GetRange() )
        self.information.SetValue(msg)      
        self.refreshList(True)   
    def ShowSelectDialig(self):
        self.selectDialog = MountDialog( self, self.fsm.drivers, self.fsm.password )
        self.selectDialog.Run()
        if self.selectDialog.exitcode == 0:
            strpath = self.selectDialog.rootPath
            if strpath in self.fsm.drivers:
                self.fsm.setCurrentDriver(strpath, self.selectDialog.password)
                self.initialed = True
                self.refreshList()
    def refreshList(self, refreshFlag = True):
        try:
            data = self.fsm.getData(refreshFlag)
            for i in range(len(data)):
                self.dm_datamodels[i].RefreshData(data[i])
                item = None
                if item is None:
                    self.views[i].SelectAll()
                    items = self.views[i].GetSelections()
                    if len(items) > 0:
                        self.views[i].UnselectAll()
                        self.views[i].Select(items[0])
                        self.views[i].SetCurrentItem(items[0])
            self.information.SetValue('idle')
            self.progress.SetValue(0)
            self.SetStatusText(self.fsm.currentDir)
        except :
            self.log(traceback.format_exc())
    def OnGotoParent(self, event):
        self.fsm.gotoParent()
        self.refreshList()
    def OnItemActivated(self, event):
        try:
            for i in range(len(self.views)):
                if self.views[i] == event.EventObject:
                    item = self.views[i].GetCurrentItem()
                    idx, target = self.dm_datamodels[i].GetItemTarget(item)
                    if target is None and idx == 0:
                        self.fsm.gotoParent()
                        self.refreshList()
                    elif target is not None:
                        flg = self.fsm.activeItem(target.name, i)
                        self.refreshList(flg)    
                    break
        except :
            self.log(traceback.format_exc())
    def OnOpen(self, event):
        try:
            item = self.views[0].GetCurrentItem()
            idx, target = self.dm_datamodels[0].GetItemTarget(item)
            if target is None and idx == 0:
                self.fsm.gotoParent()
                self.refreshList()
            elif target is not None:
                flg = self.fsm.activeItem(target.name, 0)
                self.refreshList(flg)    
        except :
            self.log(traceback.format_exc())
 
    def OnItemValueChanged1(self,event):
        try:
            for i in range(len(self.views)):
                if self.views[i] == event.EventObject:
                    item = self.views[i].GetCurrentItem()
                    _, target = self.dm_datamodels[i].GetItemTarget(item)
                    if target is not None:
                        self.refreshList(False)
                    break
            return True
        except :
            self.log(traceback.format_exc())
    def OnItemValueChanged2(self,event):
        try:
            for i in range(len(self.views)):
                if self.views[i] == event.EventObject:
                    item = self.views[i].GetCurrentItem()
                    _, target = self.dm_datamodels[i].GetItemTarget(item)
                    if target is not None:
                        self.refreshList(False)
                    break
            return True
        except :
            self.log(traceback.format_exc())
    def OnItemDragAndDrop( self, event ):
        try:
            print (event)
        except :
            self.log(traceback.format_exc())
    def OnContextMenu1(self,event):
        self.PopupMenu(self.contextMenu1, event.GetPosition())
        #event.Skip()
    def OnContextMenu2(self,event):
        
        #event.Skip()
        item  = self.views[1].GetCurrentItem() 
        _, target = self.dm_datamodels[1].GetItemTarget(item)
        if target is not None:
            if target.isFolder:
                self.PopupMenu(self.contextMenu2, event.GetPosition())
            else:
                self.PopupMenu(self.contextMenu3, event.GetPosition())
    def OnStopJob(self, event ):
        if self.currentJobThread is not None:
            while  len(self.currentJobThread) > 0:
                job = self.currentJobThread.pop()
                job.Kill()
        self.clear()
        self.stop('')
 
    def OnExit(self, event):
        """Close the frame, terminating the application."""
        self.fsm.destroy()
        self.Close(True)

    def OnGoto(self, event):
        '''change disk'''
        self.ShowSelectDialig()
    
    def OnAbout(self, event):
        """Display an About Dialog"""
        wx.MessageBox("This is a secure explorer authored by GAFS",
                      "About GS explorer",
                      wx.OK|wx.ICON_INFORMATION)

    def OnEncrypt(self, event):
        """Encrypt all files selected in the left view"""
        try:
            self.information.SetValue('')
            self.fsm.EncryptFiles(self)
        except :
            self.log(traceback.format_exc())
    def OnEncryptCM(self, event):
        try:
            items = self.views[0].GetSelections() 
            targets = []
            for item in items:
                _, target = self.dm_datamodels[0].GetItemTarget(item)
                
                if target is not None:
                    targets.append(target)
            
            self.fsm.EncryptFile(targets, self)      
        except :
            self.log(traceback.format_exc())   
    def OnDecrypt(self, event):
        """Decrypt all files selected in the left view"""
        try:
            self.information.SetValue('')
            self.fsm.DecryptFiles( self)
        except :
            self.log(traceback.format_exc())        
    def OnDecryptCM(self, event):
        try:
            items = self.views[1].GetSelections() 
            targets = []
            for item in items:
                _, target = self.dm_datamodels[1].GetItemTarget(item)
                
                if target is not None:
                    targets.append(target)
            
            self.fsm.DecryptFile(targets, self)      
        except :
            self.log(traceback.format_exc())  
    def OnEditTags(self, event ):
        try:
            item  = self.views[1].GetCurrentItem() 
            _, target = self.dm_datamodels[1].GetItemTarget(item)
            if target is not None:
                targetEditor = TagEditor( self, target )
                targetEditor.Run()
                self.fsm.updateTags([target])
                self.refreshList(False)
        except :
            self.log(traceback.format_exc())         
    def OnClearEmptyFolder(self, event):
        """clear all empty folders in the left view"""
        try:
            self.fsm.clearEmptyFolder()
            self.refreshList()
        except :
            self.log(traceback.format_exc())    
    def OnRefresh(self,event):
        '''refresh current directory'''
        self.refreshList()
        
    def OnSearchTag(self, event):
        dlg = SearchByTag(self, self.fsm.repositories[1])
        dlg.Run()
    def OnSearchName(self, event):
        dlg = SearchByName(self, self.fsm.repositories[1])
        dlg.Run()   
    def OnShowAsAlbum(self, event):
        s = self.GetSize()
        dlg = AlbumExplorer(self, s.width, s.height, self.fsm.repositories[1], self.fsm.currentDir)
        dlg.Run()          
    def OnRenameFile(self, event):
        try:
            item  = self.views[0].GetCurrentItem() 
            _, target = self.dm_datamodels[0].GetItemTarget(item)
            if target is not None:
                dlg = wx.TextEntryDialog(self, "New name",'Input a new name', target.name)  
                if dlg.ShowModal() == wx.ID_OK:      
                    response = dlg.GetValue()
                    if response and response != target.name:
                        r = RunCmd('rename "%s" "%s"'%(target.getFullPath(), response))
                        if r == 0:
                            self.refreshList()
        except :
            self.log(traceback.format_exc())     
    def OnDeleteFile(self,event):
        try:
            item  = self.views[0].GetCurrentItem() 
            _, target = self.dm_datamodels[0].GetItemTarget(item)
            if target is not None and not target.isFolder:
                dlg = wx.MessageBox( 'Make sure to delete?', 'Make sure to delete?', wx.YES_NO)  
                if dlg == wx.YES:      
                    r = RunCmd('del "%s" '%(target.getFullPath() ))
                    if r == 0:
                        self.refreshList()
        except :
            self.log(traceback.format_exc())   
    def OnDeleteFiles(self, event):
        dlg = wx.MessageBox( 'Make sure to delete?', 'Make sure to delete?', wx.YES_NO)  
        if dlg != wx.YES:    
            return         
        sels = self.views[0].GetSelections()
        for sel in sels:
            try:
                _, target = self.dm_datamodels[0].GetItemTarget(sel)
                if target is not None and not target.isFolder:
                    r = RunCmd('del "%s" '%(target.getFullPath() ))
                    if r != 0:
                        self.log('failed to delete "%s" '%(target.getFullPath() ))    
            except :
                self.log('failed to delete "%s" with exception '%(target.getFullPath() ))    
        self.refreshList()       
 
class MountDialog(wx.Dialog):
    def __init__(self, parent, drivers, password):
        wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = u'Select mount disk', pos = wx.DefaultPosition, size = wx.Size( 420, 220), style = wx.DEFAULT_DIALOG_STYLE )
        self.rootPath = None
        self.password = password
        self.drivers = drivers
        self.type = 1
        self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )
        self.exitcode = 1
        bSizer2 = wx.BoxSizer( wx.VERTICAL )
        self.rootPath = self.drivers[0]
        m_radioBox1Choices = self.drivers
        self.m_disk = wx.RadioBox( self, wx.ID_ANY, u"select disk", wx.Point( 10,-1 ), wx.Size( 400, -1 ), m_radioBox1Choices, 15, wx.RA_SPECIFY_COLS )
        #self.m_foldertype.SetSelection( 1 )
        bSizer2.Add( self.m_disk, 0, wx.ALL, 5 )
        #static text
        self.m_staticText2 = wx.StaticText( self, wx.ID_ANY, u"Please input the password:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText2.Wrap( -1 )
        bSizer2.Add( self.m_staticText2, 0, wx.ALL, 5 )
        self.m_password = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size( 350,32 ), style=wx.TE_PROCESS_ENTER )
        bSizer2.Add( self.m_password, 0, wx.ALL, 10 )
        # buttons
        gSizer1 = wx.GridSizer( 0, 5, 0, 0 )
        self.m_cancel = wx.Button( self, wx.ID_ANY, u"Cancel", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_cancel.SetBitmapPosition( wx.RIGHT )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_cancel, 1, wx.ALL, 5 )
        self.m_ok = wx.Button( self, wx.ID_ANY, u"OK", wx.DefaultPosition, wx.DefaultSize, 0 )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_ok, 3, wx.ALL, 5 )
        bSizer2.Add( gSizer1, 1, wx.EXPAND, 5 )

        self.SetSizer( bSizer2 )
        self.Layout()
        self.Centre( wx.BOTH )
        self.m_disk.Bind( wx.EVT_RADIOBOX, self.OnDiskChanged )
        self.m_cancel.Bind( wx.EVT_BUTTON, self.OnCancel )
        self.m_ok.Bind( wx.EVT_BUTTON, self.OnOK )
        self.Bind(wx.EVT_TEXT_ENTER, self.OnOK, self.m_password)
      
    def OnDiskChanged(self, event):
        s= self.m_disk.GetSelection()
        self.rootPath = self.drivers[s]
    def OnCancel(self, event):
        self.Hide()
    def OnOK(self, event ):
        self.password = self.m_password.GetValue()
        if not self.password:
            wx.MessageBox("Please input a password",
                      "Need a password")
        else:
            self.exitcode = 0
            self.Hide()
    def Run(self):
        self.exitcode = 1
        self.m_password.SetValue(self.password or '')
        self.ShowModal()
        
class TagEditor(wx.Dialog):
    def __init__(self, parent, target):
        wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = u'Edit tags', pos = wx.DefaultPosition, size = wx.Size( 420, 420), style = wx.DEFAULT_DIALOG_STYLE )
        self.target = target
        self.tags = self.splitTagStr(target.tags)
        self.drawUI( )
        self.initialList()
    def drawUI(self):
        
        self.listbox = wx.ListBox(self, id=wx.ID_ANY, pos=wx.DefaultPosition,
                size=wx.DefaultSize)
        
        #buttons0
        gSizer0 = wx.GridSizer( 0, 5, 0, 0 )
        self.m_delete = wx.Button( self, wx.ID_ANY, u"Delete", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_delete.SetBitmapPosition( wx.RIGHT )
        gSizer0.Add( 0, 1, wx.ALL, 5 )
        gSizer0.Add( self.m_delete, 1, wx.ALL, 5 )
        self.m_new = wx.Button( self, wx.ID_ANY, u"New", wx.DefaultPosition, wx.DefaultSize, 0 )
        gSizer0.Add( 0, 1, wx.ALL, 5 )
        gSizer0.Add( self.m_new, 3, wx.ALL, 5 )
        # buttons
        gSizer1 = wx.GridSizer( 0, 5, 0, 0 )
        self.m_cancel = wx.Button( self, wx.ID_ANY, u"Cancel", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_cancel.SetBitmapPosition( wx.RIGHT )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_cancel, 1, wx.ALL, 5 )
        self.m_ok = wx.Button( self, wx.ID_ANY, u"OK", wx.DefaultPosition, wx.DefaultSize, 0 )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_ok, 3, wx.ALL, 5 )
        
        
        bSizer2 = wx.BoxSizer( wx.VERTICAL )
        bSizer2.Add( self.listbox, 1, wx.ALL|wx.EXPAND, 5 )
        bSizer2.Add( gSizer0, 0, wx.EXPAND, 5 )
        bSizer2.Add( gSizer1, 0, wx.EXPAND, 5 )
        self.SetSizer( bSizer2 )
        self.Layout()
        self.Centre( wx.BOTH )
        
        self.m_cancel.Bind( wx.EVT_BUTTON, self.OnCancel )
        self.m_ok.Bind( wx.EVT_BUTTON, self.OnOK )     
        self.m_delete.Bind( wx.EVT_BUTTON, self.OnDelete )   
        self.m_new.Bind( wx.EVT_BUTTON, self.OnNew )      
    def splitTagStr(self, tags):
        if tags:
            ss = tags.split(',')
            res = []
            for s in ss:
                res.append(s.strip())
            return res
        else:
            return []
    def initialList(self):
        for tag in self.tags:
            self.listbox.Append(tag)
    def OnNew(self, event):
        dlg = wx.TextEntryDialog(self, "Tag",'Input tag', '')  
        if dlg.ShowModal() == wx.ID_OK:      
            response = dlg.GetValue()
            if response in self.tags:
                pass
            else:
                self.tags.append(response)
                self.listbox.Append(response)
    def OnDelete(self, event ):
        items = self.listbox.GetSelections()
        for item in items:
            self.tags.pop(item)
        self.listbox.Clear()
        self.initialList()       
    def OnCancel(self, event):
        self.Hide()
    def OnOK(self, event ):
        tag_str = ''
        for tag in self.tags:
            if len(tag) == 0:
                continue
            if len(tag_str) > 0:
                tag_str = tag_str + ","
            tag_str = tag_str + tag
        self.target.tags = tag_str
        self.Hide()
    def Run(self):
        self.ShowModal()
class SearchByTag(wx.Dialog):
    def __init__(self, parent, reposervice ):
        wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = u'Search tags', pos = wx.DefaultPosition, size = wx.Size( 600, 600), style = wx.DEFAULT_DIALOG_STYLE )
        self.reposervice = reposervice
        self.drawUI( )
        self.fObjs = []
    def drawUI(self):
        
        self.listbox = wx.ListBox(self)
        
        #buttons0
        gSizer0 = wx.BoxSizer(  )
        self.m_text_tag = wx.TextCtrl(self )
        gSizer0.Add( self.m_text_tag, 1, wx.ALL, 5 )
        self.m_search = wx.Button( self, wx.ID_ANY, u"Search", wx.DefaultPosition, wx.DefaultSize, 0 )
        gSizer0.Add( self.m_search, 0, wx.ALL, 5 )
        # buttons
        gSizer1 = wx.GridSizer( 0, 5, 0, 0 )
        self.m_checkout = wx.Button( self, wx.ID_ANY, u"Checkout", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_checkout.SetBitmapPosition( wx.RIGHT )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_checkout, 1, wx.ALL, 5 )
        self.m_ok = wx.Button( self, wx.ID_ANY, u"Close", wx.DefaultPosition, wx.DefaultSize, 0 )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_ok, 3, wx.ALL, 5 )
        
        
        bSizer2 = wx.BoxSizer( wx.VERTICAL )
        
        bSizer2.Add( gSizer0, 0, wx.EXPAND, 5 )
        bSizer2.Add( self.listbox, 1, wx.ALL|wx.EXPAND, 5 )
        bSizer2.Add( gSizer1, 0, wx.EXPAND, 5 )
        self.SetSizer( bSizer2 )
        self.Layout()
        self.Centre( wx.BOTH )
        
        self.m_checkout.Bind( wx.EVT_BUTTON, self.OnCheckout )
        self.m_ok.Bind( wx.EVT_BUTTON, self.OnOK )     
        self.m_search.Bind( wx.EVT_BUTTON, self.OnSearch )   
 
    def initialList(self):
        self.listbox.Clear()
        for tag in self.fObjs:
            self.listbox.Append('[%s]%s'%(tag.tags, tag.getFullPath()))
    def OnSearch(self, event):
        tag = self.m_text_tag.GetValue()
        if tag:      
            self.fObjs = self.reposervice.getByTag(tag, 100)
            self.initialList()
   
    def OnCheckout(self, event):
        idxes = self.listbox.GetSelections()
        files = []
        for idx in idxes:
            file = self.fObjs[idx]
            files.append(file)
        self.reposervice.setAsynCall('checkout', files, None)
    def OnOK(self, event ):
        self.Hide()
    def Run(self):
        self.ShowModal() 
class SearchByName(wx.Dialog):
    def __init__(self, parent, reposervice ):
        wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = u'Search name', pos = wx.DefaultPosition, size = wx.Size( 600, 600), style = wx.DEFAULT_DIALOG_STYLE )
        self.reposervice = reposervice
        self.drawUI( )
        self.fObjs = []
    def drawUI(self):
        
        self.listbox = wx.ListBox(self)
        
        #buttons0
        gSizer0 = wx.BoxSizer(  )
        self.m_text_tag = wx.TextCtrl(self )
        gSizer0.Add( self.m_text_tag, 1, wx.ALL, 5 )
        self.m_search = wx.Button( self, wx.ID_ANY, u"Search", wx.DefaultPosition, wx.DefaultSize, 0 )
        gSizer0.Add( self.m_search, 0, wx.ALL, 5 )
        # buttons
        gSizer1 = wx.GridSizer( 0, 5, 0, 0 )
        self.m_checkout = wx.Button( self, wx.ID_ANY, u"Checkout", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_checkout.SetBitmapPosition( wx.RIGHT )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_checkout, 1, wx.ALL, 5 )
        self.m_ok = wx.Button( self, wx.ID_ANY, u"Close", wx.DefaultPosition, wx.DefaultSize, 0 )
        gSizer1.Add( 0, 1, wx.ALL, 5 )
        gSizer1.Add( self.m_ok, 3, wx.ALL, 5 )
        
        
        bSizer2 = wx.BoxSizer( wx.VERTICAL )
        
        bSizer2.Add( gSizer0, 0, wx.EXPAND, 5 )
        bSizer2.Add( self.listbox, 1, wx.ALL|wx.EXPAND, 5 )
        bSizer2.Add( gSizer1, 0, wx.EXPAND, 5 )
        self.SetSizer( bSizer2 )
        self.Layout()
        self.Centre( wx.BOTH )
        
        self.m_checkout.Bind( wx.EVT_BUTTON, self.OnCheckout )
        self.m_ok.Bind( wx.EVT_BUTTON, self.OnOK )     
        self.m_search.Bind( wx.EVT_BUTTON, self.OnSearch )   
 
    def initialList(self):
        self.listbox.Clear()
        for tag in self.fObjs:
            self.listbox.Append('[%s]%s'%(tag.tags, tag.getFullPath()))
    def OnSearch(self, event):
        tag = self.m_text_tag.GetValue()
        if tag:      
            self.fObjs = self.reposervice.getByName(tag, 100)
            self.initialList()
   
    def OnCheckout(self, event):
        idxes = self.listbox.GetSelections()
        files = []
        for idx in idxes:
            file = self.fObjs[idx]
            files.append(file)
        self.reposervice.setAsynCall('checkout', files, None)

    def OnOK(self, event ):
        self.Hide()
    def Run(self):
        self.ShowModal() 
class AlbumExplorer(wx.Dialog):
    def __init__(self, parent, w, h, reposervice, currDir = None):
        # ensure the parent's __init__ is called
        wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = u'Album explorer', pos = (0,0),  size = (w-10,h-10), style =   wx.DEFAULT_DIALOG_STYLE )
        self.reposervice = reposervice
        self.Bind( wx.EVT_INIT_DIALOG, self.OnInitial )
        self.showSize = 10
        self.currDir = currDir
        self.size = None
        self.unitsize = 10
        self.data = []
        self.listItems = []
        self.buttons = []
        self.hsizer = None
        self.gridsizer = None
        self.listbox = None
        self.panel = None
        self.SetBackgroundColour('white')
        self.SetLayoutAdaptationMode(wx.DIALOG_ADAPTATION_MODE_ENABLED)
    def setGridSizer(self, num):
         
        if self.listbox is None:
            self.listbox = wx.ListBox(self, pos=(5,5), size=(self.size.width - 15 ,150))
            self.listbox.Bind(wx.EVT_LISTBOX_DCLICK , self.OnClickListBox)
 
        else:
            self.listbox.Clear()
        self.unitsize = int( (self.size.width - 30) / self.showSize ) - 5
        if self.panel is not None:
            self.panel.DestroyChildren()
            self.gridsizer.SetCols(self.showSize)

        else:
            self.panel = wx.ScrolledWindow(self,  pos=(5,160), size = (self.size.width - 25, self.size.height - 180 ), style=wx.ALWAYS_SHOW_SB )
            self.panel.SetScrollbars(10, 20, 600, 1000)
            self.panel.EnableScrolling(True, True)
            self.panel.SetBackgroundColour('white')
  
    def addPicture(self, obj, idx ):
        y = int(idx / self.showSize)
        x = idx - y * self.showSize
        y = y * self.unitsize + 5
        x = x * self.unitsize + 5
        if obj is None:
            bmpbtn = wx.Button(self.panel, id = wx.ID_ANY, label = '..', pos=(x,y), size = (self.unitsize,self.unitsize))
        elif obj['picture'] is not None and os.path.exists(obj['picture']):
            if obj['ext'] == '.png':
                pic = wx.Image(obj['picture'],wx.BITMAP_TYPE_PNG)
            else:
                pic = wx.Image(obj['picture'],wx.BITMAP_TYPE_JPEG) 
            w = pic.GetWidth() 
            h = pic.GetHeight() 
            if w > h :
                por = self.unitsize / w
            else:
                por = self.unitsize / h
                
            pic.Rescale( int(por*w), int(por*h))
            pic = pic.ConvertToBitmap()
            bmpbtn = wx.BitmapButton(self.panel, id = wx.ID_ANY, bitmap = pic , pos=(x,y), size = (self.unitsize,self.unitsize))
            self.buttons.append( bmpbtn)
        else:
            bmpbtn = wx.Button(self.panel, id = wx.ID_ANY, label = obj['name'], pos=(x,y), size = (self.unitsize,self.unitsize))
            self.buttons.append( bmpbtn)
        bmpbtn.Bind( wx.EVT_BUTTON, self.OnClickButton )     
 
    def refreshCurrentFolder(self ):
        children = self.reposervice.getChildren(self.currDir)
        self.data = []
        self.buttons = []
        for child in children:
            self.generateShowObj(child, self.data)
        self.setGridSizer(len(self.data))
        idx = 0
        for obj in self.data:
            self.addPicture(obj,idx)
            idx = idx + 1       
        self.addPicture(None, idx)   
        self.panel.Layout()
        self.Layout()
    def OnInitial(self, event ):
        self.size = self.GetSize()
        self.refreshCurrentFolder()
    def compareName(self, name1, name2 ):
        if len(name1) < len( name2 ):
            if name1 in name2[0:len(name1)]:
                return True
        else:
            if name2 in name1[0:len(name2)]:
                return True
        return False
    def findName(self, name, objs ):
        for obj in objs:
            if self.compareName(name, obj['name']):
                return obj
        return None
    def getPicture(self, fobj):
        if fobj.isFolder:
            children = self.reposervice.getChildren(fobj.getFullPath())
            for c in children:
                names = os.path.splitext(c.name.lower())
                if names[1] == '.png' or names[1] =='.jpg':
                    return (c.getDummyPath(), names[1])
        else:
            names = os.path.splitext(fobj.name.lower())
            if names[1] == '.png' or names[1] == '.jpg':
                return ( fobj.getDummyPath(), names[1] )
        return (None, None)
    def generateShowObj(self, fobj, objs ):
        names = os.path.splitext(fobj.name.lower())
        showObj = self.findName(names[0], objs)
        if showObj is None:
            showObj = dict()
            showObj['name'] = names[0]
            showObj['picture'], ext = self.getPicture(fobj)
            showObj['ext'] = ext or names[1]
            showObj['obj'] = []
            showObj['obj'].append( fobj )
            objs.append(showObj)
        else:
            showObj['obj'].append( fobj )
            if showObj['picture'] is None:
                showObj['picture'], ext = self.getPicture(fobj)
                if showObj['picture'] is not None:
                    showObj['ext'] = ext
    def OnClickButton(self, event):
        self.listbox.Clear()
        for i in range(len(self.buttons)):
            if event.EventObject.GetId() == self.buttons[i].GetId():
                self.listItems = self.data[i]['obj']
                
                for obj in self.listItems:
                    self.listbox.Append('%s'%(obj.getFullPath()))
                return
        names  = os.path.split(self.currDir)
        self.currDir = names[0]
        self.refreshCurrentFolder()
        
    def OnClickListBox(self, event):
        itemIdx = self.listbox.GetSelection()
        item = self.listItems[itemIdx]
        if item.isFolder:
            self.currDir = item.getFullPath()
            self.refreshCurrentFolder()
    def OnOK(self, event ):
        self.Hide()
    def Run(self):
        self.ShowModal()

if __name__ == '__main__':
    # When this module is run (not imported) then create the app, the
    # frame, show it, and start the event loop.
    multiprocessing.freeze_support()
    app = wx.App()
    frm = Explorer( None )
 
    frm.ShowSelectDialig()
    if frm.initialed:
        frm.fsm.Run()
        frm.Show()
        app.MainLoop() 
    frm.fsm.Stop()
