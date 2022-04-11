# -*- coding:utf-8 -*-

import os
import wx
import wx.adv
import wx.lib.filebrowsebutton as filebrowse
from win32con import MOD_CONTROL, VK_F2
from threading import Thread
from datetime import datetime
from configparser import ConfigParser
from PIL import Image, ImageGrab
from imageio import mimsave
from icon import get_fp

class MainFrame(wx.Frame):
    """屏幕录像机主窗口"""
    
    MENU_REC  = wx.NewIdRef()        # 开始/停止录制
    MENU_SHOW   = wx.NewIdRef()      # 显示窗口
    MENU_HIDE   = wx.NewIdRef()      # 窗口最小化
    MENU_STOP   = wx.NewIdRef()      # 停止录制
    MENU_CONFIG = wx.NewIdRef()      # 设置
    MENU_FOLFER = wx.NewIdRef()      # 打开输出目录
    MENU_EXIT   = wx.NewIdRef()      # 退出

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1, "", style=wx.FRAME_SHAPED|wx.FRAME_NO_TASKBAR|wx.STAY_ON_TOP)
        
        im = Image.open(get_fp()) # 读图标的二进制数据，转为PIL对象
        bmp = wx.Bitmap.FromBufferRGBA(im.size[0], im.size[1], im.tobytes()) # PIL对象转为wx.Bitmap对象
        icon = wx.Icon() # 创建空图标
        icon.CopyFromBitmap(bmp) # wx.Bitmap数据复制到wx.Icon对象
        
        x, y, w, h = wx.ClientDisplayRect() # 屏幕显示区域
        x0, y0 = (w-820)//2, (h-620)//2 # 录像窗口位置（默认大小820x620，边框10像素）
        
        self.SetPosition((x, y)) # 无标题窗口最大化：设置位置
        self.SetSize((w, h)) # 无标题窗口最大化：设置大小
        self.SetDoubleBuffered(True) # 启用双缓冲
        self.taskBar = wx.adv.TaskBarIcon()  # 添加系统托盘
        self.taskBar.SetIcon(icon, "屏幕录像机")
        
        self.box = [x0, y0, 820, 620]       # 屏幕录像窗口大小
        self.xy = None                      # 鼠标左键按下的位置
        self.recording = False              # 正在录制标志
        self.saveing = False                # 正在生成GIF标志
        self.imgs = list()                  # 每帧的图片列表
        self.timer = wx.Timer(self)         # 创建录屏定时器
        self.cfg = self.ReadConfig()        # 读取配置项
        self.SetWindowShape()               # 设置不规则窗口
        
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)                                # 鼠标事件
        self.Bind(wx.EVT_PAINT, self.OnPaint)                                       # 窗口重绘
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBG)                          # 擦除背景
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)                           # 定时器
        
        self.taskBar.Bind(wx.adv.EVT_TASKBAR_RIGHT_UP, self.OnTaskBar)              # 右键单击托盘图标
        self.taskBar.Bind(wx.adv.EVT_TASKBAR_LEFT_UP, self.OnTaskBar)               # 左键单击托盘图标
        self.taskBar.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.OnTaskBar)           # 左键双击托盘图标
        
        self.taskBar.Bind(wx.EVT_MENU, self.OnRec, id=self.MENU_REC)                # 开始/停止录制
        self.taskBar.Bind(wx.EVT_MENU, self.OnShow, id=self.MENU_SHOW)              # 显示窗口
        self.taskBar.Bind(wx.EVT_MENU, self.OnHide, id=self.MENU_HIDE)              # 隐藏窗口
        self.taskBar.Bind(wx.EVT_MENU, self.OnOpenFolder, id=self.MENU_FOLFER)      # 打开输出目录
        self.taskBar.Bind(wx.EVT_MENU, self.OnConfig, id=self.MENU_CONFIG)          # 设置
        self.taskBar.Bind(wx.EVT_MENU, self.OnExit, id=self.MENU_EXIT)              # 退出
        
        self.RegisterHotKey(self.MENU_REC, MOD_CONTROL, VK_F2)                      # 注册热键
        self.Bind(wx.EVT_HOTKEY, self.OnRec, id=self.MENU_REC)                      # 开始/停止录制热键
    
    def ReadConfig(self):
        """读取配置文件"""

        config = ConfigParser()

        if os.path.isfile("recorder.ini"):
            config.read("recorder.ini")
        else:
            out_path = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'out')
            if not os.path.exists(out_path):
                os.mkdir(out_path)
            
            config.read_dict({"recoder":{"fps":10, "frames":100, "loop":0, "outdir":out_path}})
            config.write(open("recorder.ini", "w"))

        return config

    def SetWindowShape(self):
        """设置窗口形状"""
        
        path = wx.GraphicsRenderer.GetDefaultRenderer().CreatePath()
        
        self.Round = 8 # 圆角矩形_圆半径
        self.Border_thicknes = 10 # 边框_厚度
        
        path.AddRoundedRectangle(self.box[0],
                                    self.box[1],
                                    self.box[2],
                                    self.box[3],
                                    self.Round) # 外层,圆角矩形
                                    
        path.AddRectangle(self.box[0] + self.Border_thicknes,
                            self.box[1] + self.Border_thicknes,
                            self.box[2] - self.Border_thicknes * 2,
                            self.box[3] - self.Border_thicknes * 2) # 内层,矩形

        # 路径重叠部分会进行差集计算
    
        self.SetShape(path) # 设置异形窗口形状

    def OnMouse(self, evt):
        """鼠标事件"""
        
        if evt.EventType == wx.EVT_LEFT_DOWN.evtType[0]: #左键按下
            if self.box[0]+10 <= evt.x <= self.box[0]+self.box[2]-10 and self.box[1]+10 <= evt.y <= self.box[1]+self.box[3]-10:
                self.xy = None
            else:
                self.xy = (evt.x, evt.y)
        elif evt.EventType == wx.EVT_LEFT_UP.evtType[0]: #左键弹起
            self.xy = None
        elif evt.EventType == wx.EVT_MOTION.evtType[0]:  #鼠标移动
            if self.box[0] < evt.x < self.box[0]+10:
                if evt.LeftIsDown() and self.xy:
                    dx, dy = evt.x-self.xy[0], evt.y-self.xy[1]
                    self.box[0] += dx
                    self.box[2] -= dx
                if self.box[1] < evt.y < self.box[1]+10:
                    self.SetCursor(wx.Cursor(wx.CURSOR_SIZENWSE))
                    if evt.LeftIsDown() and self.xy:
                        self.box[1] += dy
                        self.box[3] -= dy
                elif evt.y > self.box[1]+self.box[3]-10:
                    self.SetCursor(wx.Cursor(wx.CURSOR_SIZENESW))
                    if evt.LeftIsDown() and self.xy:
                        self.box[3] += dy
                else:
                    self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE))
            elif self.box[0]+self.box[2]-10 < evt.x < self.box[0]+self.box[2]:
                if evt.LeftIsDown() and self.xy:
                    dx, dy = evt.x-self.xy[0], evt.y-self.xy[1]
                    self.box[2] += dx
                if self.box[1] < evt.y < self.box[1]+10:
                    self.SetCursor(wx.Cursor(wx.CURSOR_SIZENESW))
                    if evt.LeftIsDown() and self.xy:
                        self.box[1] += dy
                        self.box[3] -= dy
                elif evt.y > self.box[1]+self.box[3]-10:
                    self.SetCursor(wx.Cursor(wx.CURSOR_SIZENWSE))
                    if evt.LeftIsDown() and self.xy:
                        self.box[3] += dy
                else:
                    self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE))
            elif self.box[1] < evt.y < self.box[1]+10:
                self.SetCursor(wx.Cursor(wx.CURSOR_SIZENS))
                if evt.LeftIsDown() and self.xy:
                    dx, dy = evt.x-self.xy[0], evt.y-self.xy[1]
                    self.box[1] += dy
                    self.box[3] -= dy
            elif self.box[1]+self.box[3]-10 < evt.y < self.box[1]+self.box[3]:
                self.SetCursor(wx.Cursor(wx.CURSOR_SIZENS))
                if evt.LeftIsDown() and self.xy:
                    dx, dy = evt.x-self.xy[0], evt.y-self.xy[1]
                    self.box[3] += dy
            
            if self.box[0] < 0:
                self.box[2] += self.box[0]
                self.box[0] = 0
            if self.box[1] < 0:
                self.box[3] += self.box[1]
                self.box[1] = 0
            
            w, h = self.GetSize()
            if self.box[2] > w:
                self.box[2] = w
            if self.box[3] > h:
                self.box[3] = h
            
            self.xy = (evt.x, evt.y)
            self.isFullScreen = self.GetSize() == (self.box[2],self.box[3])
            self.SetWindowShape()
            self.Refresh()

    def OnPaint(self, evt):
        """窗口重绘事件处理"""
        
        dc = wx.PaintDC(self)
        dc.SetBrush(wx.RED_BRUSH if self.recording else wx.GREEN_BRUSH)
        #w, h = self.GetSize()
        dc.DrawRectangle(self.box[0] - 2,self.box[1] - 2,self.box[2] + 2,self.box[3] + 2) # 起点/终点各有2px的偏移,原因未知

    def OnEraseBG(self, evt):
        """擦除背景事件处理"""

        pass

    def OnTaskBar(self, evt):
        """托盘图标操作事件处理"""
        
        # 创建菜单
        menu = wx.Menu()
        menu.Append(self.MENU_REC, "开始/停止(Ctrl+F2)")
        menu.AppendSeparator()
        if self.IsIconized():
            menu.Append(self.MENU_SHOW, "显示屏幕录像窗口")
        else:
            menu.Append(self.MENU_HIDE, "最小化至任务托盘")
        menu.AppendSeparator()
        menu.Append(self.MENU_FOLFER, "打开输出目录")
        menu.Append(self.MENU_CONFIG, "设置录像参数")
        menu.AppendSeparator()
        menu.Append(self.MENU_EXIT, "退出")

        # 设置状态
        if self.recording:
            menu.Enable(self.MENU_CONFIG, False)
            menu.Enable(self.MENU_EXIT, False)
        else:
            menu.Enable(self.MENU_CONFIG, True)
            menu.Enable(self.MENU_EXIT, True)

        self.taskBar.PopupMenu(menu)
        menu.Destroy()

    def OnTimer(self, evt):
        """定时器事件处理：截图"""
        
        img = ImageGrab.grab((self.box[0]+10, self.box[1]+10, self.box[0]+self.box[2]-10, self.box[1]+self.box[3]-10))
        self.imgs.append(img)

        if len(self.imgs) >= self.cfg.getint("recoder", "frames"):
            self.StopRec()

    def OnShow(self, evt):
        """显示窗口"""

        self.Iconize(False)

    def OnHide(self, evt):
        """隐藏窗口"""

        self.Iconize(True)

    def OnRec(self, evt):
        """开始/停止录制菜单事件处理"""
        
        if self.recording: # 停止录制
            self.StopRec()
        else: # 开始录制
            self.StartRec()

    def StartRec(self):
        """开始录制"""

        self.OnShow(None)
        self.recording = True
        self.timer.Start(1000/self.cfg.getint("recoder", "fps")) # 启动定时器
        self.Refresh() # 刷新窗口

    def StopRec(self):
        """停止录制"""
        
        self.timer.Stop() # 停止定时器
        self.recording = False
        self.OnHide(None)

        # 启动生成GIF线程
        t = Thread(target=self.CreateGif)
        t.setDaemon(True)
        t.start()
        
        # 弹出模态的等待对话窗
        count, count_max = 0, 100
        style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_ESTIMATED_TIME | wx.PD_REMAINING_TIME | wx.PD_AUTO_HIDE
        dlg = wx.ProgressDialog("生成GIF", "共计%d帧，正在渲染，请稍候..."%len(self.imgs), parent=self, style=style)
        
        while self.saveing and count < count_max:
            dlg.Pulse()
            wx.MilliSleep(100)
        
        dlg.Destroy() # 关闭等待生成GIF结束的对话窗
        self.OnOpenFolder(None) # 打开动画文件保存路径

    def CreateGif(self):
        """生成gif动画线程"""

        self.saveing = True # 生成gif动画开始
        dt = datetime.now().strftime("%Y%m%d%H%M%S")
        filePath = os.path.join(self.cfg.get("recoder", "outdir"), "%s.gif"%dt)
        fps = self.cfg.getint("recoder", "fps")
        loop = self.cfg.getint("recoder", "loop")
        mimsave(filePath, self.imgs, format='GIF', fps=fps, loop=loop)
        self.imgs = list() # 清空截屏记录
        self.saveing = False # 生成gif动画结束

    def OnOpenFolder(self, evt):
        """打开输出目录"""

        outdir = self.cfg.get("recoder", "outdir")
        os.system("explorer %s" % outdir)

    def OnConfig(self, evt):
        """设置菜单事件处理"""
        
        dlg = ConfigDlg(self,
            self.cfg.getint("recoder", "fps"),
            self.cfg.getint("recoder", "frames"),
            self.cfg.getint("recoder", "loop"),
            self.cfg.get("recoder", "outdir")
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            self.cfg.set("recoder", "fps", str(dlg.fps.GetValue()))
            self.cfg.set("recoder", "frames", str(dlg.frames.GetValue()))
            self.cfg.set("recoder", "loop", str(dlg.loop.GetValue()))
            self.cfg.set("recoder", "outdir", dlg.GetOutDir())
            self.cfg.write(open("recorder.ini", "w"))
        
        dlg.Destroy() # 销毁设置对话框

    def OnExit(self, evt):
        """退出菜单事件处理"""
        
        self.taskBar.RemoveIcon() # 从托盘删除图标
        self.Destroy()
        wx.Exit()


class ConfigDlg(wx.Dialog):
    """录像参数设置窗口"""

    def __init__(self, parent, fps, frames, loop, outdir):
        """ConfigDlg的构造函数"""

        wx.Dialog.__init__(self, parent, -1, "设置录像参数", size=(400, 270))
        
        sizer = wx.BoxSizer() # 创建布局管理器
        grid = wx.GridBagSizer(10, 10)
        subgrid = wx.GridBagSizer(10, 10)

        # 帧率
        text = wx.StaticText(self, -1, "帧率：")
        grid.Add(text, (0, 0), flag=wx.ALIGN_RIGHT|wx.TOP, border=3)

        self.fps = wx.SpinCtrl(self, -1, size=(80,-1))
        self.fps.SetValue(fps)
        grid.Add(self.fps, (0, 1), flag=wx.LEFT, border=8)

        # 最大帧数
        text = wx.StaticText(self, -1, "最大帧数")
        grid.Add(text, (1, 0), flag=wx.ALIGN_RIGHT|wx.TOP, border=3)

        self.frames = wx.SpinCtrl(self, -1, size=(80,-1))
        self.frames.SetValue(frames)
        grid.Add(self.frames, (1, 1), flag=wx.LEFT, border=8)

        # 循环次数
        text = wx.StaticText(self, -1, "循环次数")
        grid.Add(text, (2, 0), flag=wx.ALIGN_RIGHT|wx.TOP, border=3)

        self.loop = wx.SpinCtrl(self, -1, size=(80,-1))
        self.loop.SetValue(loop)
        grid.Add(self.loop, (2, 1), flag=wx.LEFT, border=8)
        
        # 输出路径
        text = wx.StaticText(self, -1, "输出目录")
        grid.Add(text, (3, 0), flag=wx.TOP, border=8)
        self.outdir = filebrowse.DirBrowseButton(self, -1, labelText="", startDirectory=outdir, buttonText="浏览", toolTip="请选择输出路径")
        self.outdir.SetValue(outdir)
        grid.Add(self.outdir, (3, 1), flag=wx.EXPAND, border=0)

        okBtn = wx.Button(self, wx.ID_OK, "确定")
        subgrid.Add(okBtn, (0, 0), flag=wx.ALIGN_RIGHT)
        canelBtn = wx.Button(self, wx.ID_CANCEL, "取消")
        subgrid.Add(canelBtn, (0, 1))
        grid.Add(subgrid, (4, 0), (1, 2), flag=wx.ALIGN_CENTER|wx.TOP, border=10)

        # 界面总成
        grid.AddGrowableCol(1)
        sizer.Add(grid, 1, wx.EXPAND|wx.ALL, 20)
        self.SetSizer(sizer)
        self.Layout()
        self.CenterOnScreen()

class MainApp(wx.App):

    def OnInit(self):
        self.SetAppName("Hello World")
        self.frame = MainFrame(None)
        self.frame.Show()
        
        return True

if __name__ == '__main__':
    app = MainApp()
    app.MainLoop()
