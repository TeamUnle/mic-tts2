import sounddevice as sd
import soundfile as sf
import numpy as np

class Sound:
    def __init__(self, path, volume, device=None):
        self.volume = volume
        self.device = device
        self.load_audio(path)

    def set_volume(self,value):
        self.volume = value

    def load_audio(self, path: str):
        self.audio_file = sf.SoundFile(path)
        self.audio_data = self.audio_file.read()
        self.audio_file.close()
        self.tot_frames = len(self.audio_data)
        self.last_frame = 0
        self.num_channels = len(self.audio_data.shape)
        print(f'audio channels: {self.num_channels}')
        if self.num_channels==1:
            self.audio_data = np.column_stack([self.audio_data,self.audio_data])

    def callback_closure(self):
        def callback(data_out: np.ndarray, frames: int, time, status: sd.CallbackFlags) -> None:
            assert not status
            end_frame = self.last_frame + frames
            if(end_frame<=self.tot_frames):
                data_out[:] = self.volume * self.audio_data[self.last_frame:end_frame,]
            else:
                end_frame = end_frame - self.tot_frames
                tmp1 = self.audio_data[self.last_frame:,]
                tmp2 = self.audio_data[:end_frame,]
                if (tmp1.shape[0]==0):
                    data_out[:] = self.volume * tmp2
                elif (tmp2.shape[0]==0):
                    data_out[:] = self.volume * tmp1
                else:
                    data_out[:] = self.volume * np.concatenate(tmp1,tmp2)
            self.last_frame = end_frame
        return callback

    def play(self):
        self.stream = sd.OutputStream(
            device=self.device,
            samplerate=self.audio_file.samplerate,
            channels=2,
            callback=self.callback_closure()
        )
        self.stream.start()
    
    def stop(self):
        self.stream.stop()

    def __del__(self):
        self.stream.close(ignore_errors=True)