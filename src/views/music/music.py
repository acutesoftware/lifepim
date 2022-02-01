# music.py


from PyQt5.QtCore import *
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QAction 
from PyQt5.QtWidgets import QTextEdit 
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget
#from PyQt5.QtWidgets import QMediaPlaylist
#from PyQt5.QtWidgets import QMediaContent
#from PyQt5.QtWidgets import QMediaPlayer
from PyQt5.QtCore import QSettings

from PyQt5.QtMultimedia import QMediaPlaylist, QMediaContent, QMediaPlayer

"""
usage from main GUI

self.musicWidg = lpMusicWidget()
self.musicWidg.play_music_file(filename)

"""

class lpMusicWidget(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        self.visWidget = QVBoxLayout(self)  # was HBox
        self.player = QMediaPlayer(self)
        self.playlist = QMediaPlaylist(self)
        
        self.lbl_cur_file = QTextEdit('currently playing no music')
        self.cur_sound = None
        self.visWidget.addWidget(self.lbl_cur_file)

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