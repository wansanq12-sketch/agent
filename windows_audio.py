"""Play downloaded speech through Qt Multimedia, independent of WebEngine codecs."""
import base64
import io
import math
import struct
import wave
from PySide6.QtCore import QBuffer, QIODevice, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

def test_tone():
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
        audio.writeframes(b''.join(struct.pack('<h', int(3500 * math.sin(2 * math.pi * 660 * i / 24000))) for i in range(7200)))
    return output.getvalue()

class AudioPlayback:
    def __init__(self, parent, callback):
        self.parent = parent; self.callback = callback; self.player = None
        self.output = None; self.buffer = None; self.sequence = None

    def stop(self):
        self.sequence = None
        if self.player:
            self.player.stop(); self.player.setSource(QUrl()); self.player.deleteLater()
        if self.buffer:
            self.buffer.close(); self.buffer.deleteLater()
        if self.output:
            self.output.deleteLater()
        self.player = self.buffer = self.output = None

    def notify(self, sequence, message='', done=False):
        if self.sequence == sequence:
            self.callback(sequence, message, done)

    def play(self, encoded, volume, sequence, tone=False):
        self.stop(); self.sequence = sequence
        if not QMediaDevices.audioOutputs():
            self.notify(sequence, 'Windows 没有可用的音频输出设备，请连接扬声器或耳机', True); return
        try:
            data = test_tone() if tone else base64.b64decode(encoded, validate=True)
            if not data or len(data) > 8_000_000:
                raise ValueError('invalid audio')
        except (ValueError, TypeError):
            self.notify(sequence, '收到的语音音频无效，请重新试听', True); return
        self.output = QAudioOutput(self.parent)
        self.output.setVolume(max(0, min(1, volume / 100)))
        self.buffer = QBuffer(self.parent); self.buffer.setData(data)
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        player = QMediaPlayer(self.parent); self.player = player
        player.setAudioOutput(self.output)
        player.errorOccurred.connect(lambda *_: self.notify(sequence, 'Windows 音频播放失败，请检查音量合成器和输出设备', True))
        player.mediaStatusChanged.connect(lambda status: self.notify(sequence, '播放完成', True) if status == QMediaPlayer.MediaStatus.EndOfMedia else None)
        player.playbackStateChanged.connect(lambda state: self.notify(sequence, '正在播放；听不到时请检查 Windows 音量合成器中夜璃的音量与输出设备') if state == QMediaPlayer.PlaybackState.PlayingState else None)
        player.setSourceDevice(self.buffer, QUrl('test.wav' if tone else 'speech.mp3'))
        player.play()
