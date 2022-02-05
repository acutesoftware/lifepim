# music.py


from PyQt5.QtCore import *

from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QAction 
from PyQt5.QtWidgets import QTextEdit 
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QStyle
#from PyQt5.QtWidgets import QMediaPlaylist
#from PyQt5.QtWidgets import QMediaContent
#from PyQt5.QtWidgets import QMediaPlayer
from PyQt5.QtCore import QSettings
from PyQt5.QtCore import pyqtSignal

from PyQt5.QtMultimedia import QMediaPlaylist, QMediaContent, QMediaPlayer

"""
usage from main GUI

self.musicWidg = lpMusicWidget()
self.musicWidg.play_music_file(filename)

"""

class lpMusicWidget(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        self.visWidget = QHBoxLayout(self)  # was HBox
        self.player = QMediaPlayer(self)
        self.playlist = QMediaPlaylist(self)
        
        self.lbl_cur_file = QTextEdit('currently playing no music')

        self.play = pyqtSignal()
        self.pause = pyqtSignal()
        self.stop = pyqtSignal()
    
        self.playButton = QToolButton(clicked=self.playClicked, toolTip = "Play")
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

        self.stopButton = QToolButton(clicked=self.player.stop, toolTip = "Stop")
        self.stopButton.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stopButton.setEnabled(False)

        #-- buttons layout
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(self.stopButton)
        button_layout.addWidget(self.playButton)        


        self.cur_sound = None
        #self.visWidget.addWidget(self.lbl_cur_file)
        self.visWidget.addWidget(self.playButton)
        self.visWidget.addWidget(self.stopButton)
        #self.visWidget.setLayout(button_layout)

        self.resize(900,900)
        self.settings = QSettings('LifePIM_Desktop', 'Music')

    def setParent(self, parentUI):
        self.parentUI = parentUI  # this is a frame
        #parentUI.setCentralWidget(self.table)
        self.show()


    def play_music_file(self, fname):
        print('playing song - ' + fname)
        self.cur_sound = QMediaContent(QUrl(fname))

        self.player.setMedia(self.cur_sound)

        #self.playlist.addMedia(QMediaContent(QUrl.fromLocalFile(fname)))


        #self.player.setPlaylist(self.playlist)
        #self.player.playlist().setCurrentIndex(0)
        self.player.play()

    def playClicked(self):
        if self.playerState in (QMediaPlayer.StoppedState, QMediaPlayer.PausedState):
            self.play.emit()
        elif self.playerState == QMediaPlayer.PlayingState:
            self.pause.emit()
