"""Opt-in online speech. Only the supplied utterance leaves this machine."""
import asyncio
import base64
import threading

PREVIEW_TEXT = '哥哥，我在这里。休息一下吧，接下来让我陪着你，慢慢来就好。'
VOICES = {
    'zh-CN-XiaoxiaoNeural': '晓晓 · 普通话女声',
    'zh-CN-XiaoyiNeural': '晓伊 · 普通话女声',
    'zh-TW-HsiaoChenNeural': '晓臻 · 台湾国语女声',
    'zh-TW-HsiaoYuNeural': '晓雨 · 台湾国语女声',
}

_BUSY = threading.BoundedSemaphore(2)

async def _audio(text, rate, voice):
    import edge_tts
    speaker = edge_tts.Communicate(text, voice,
                                   rate=f'{rate - 108:+d}%', pitch='+2Hz')
    audio = bytearray()
    async for chunk in speaker.stream():
        if chunk['type'] == 'audio':
            audio.extend(chunk['data'])
            if len(audio) > 8_000_000:
                raise ValueError('语音内容过长，请缩短回复')
    if not audio:
        raise ValueError('在线服务没有返回声音，请重试')
    return bytes(audio)

def synthesize(text, settings, preview=None):
    preview = preview or {}
    if preview.get('enabled') is True:
        if preview.get('consent') is not True:
            raise ValueError('请先勾选在线语音授权，再试听')
        text = PREVIEW_TEXT
        settings = {**settings, 'voice_neural': True, 'voice_online_consent': True,
                    'voice_choice': preview.get('voice'),
                    'voice_rate': preview.get('rate', settings.get('voice_rate', 100))}
    if not settings.get('voice_neural', True) or not settings.get('voice_online_consent', False):
        raise ValueError('请在声音设置中允许将待朗读文字发送至微软，保存后再试听')
    if not isinstance(text, str) or not text.strip() or len(text) > 6000:
        raise ValueError('朗读文字应为 1 至 6000 字')
    voice = settings.get('voice_choice', 'zh-CN-XiaoxiaoNeural')
    if voice not in VOICES:
        raise ValueError('请选择列表中的声音')
    if not _BUSY.acquire(blocking=False):
        raise ValueError('正在生成声音，请稍后重试')
    try:
        rate = max(60, min(160, int(settings.get('voice_rate', 100))))
        audio = asyncio.run(asyncio.wait_for(_audio(text, rate, voice), timeout=45))
        return {'audio': base64.b64encode(audio).decode('ascii'), 'mime': 'audio/mpeg'}
    except ImportError:
        raise ValueError('缺少自然语音组件，请更新软件或安装 edge-tts') from None
    except ValueError:
        raise
    except Exception:
        raise ValueError('自然语音服务暂时不可用，请检查网络后重试') from None
    finally:
        _BUSY.release()
