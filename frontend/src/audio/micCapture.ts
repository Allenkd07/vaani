export interface MicCapture {
  stop: () => Promise<void>;
}

/** Streams the microphone as 16 kHz PCM16 chunks (~100 ms each). */
export async function startMicCapture(
  onChunk: (pcm: ArrayBuffer) => void,
  onLevel: (level: number) => void,
): Promise<MicCapture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const context = new AudioContext();
  await context.audioWorklet.addModule("/pcm-recorder.worklet.js");

  const source = context.createMediaStreamSource(stream);
  const recorder = new AudioWorkletNode(context, "pcm-recorder");
  recorder.port.onmessage = (event: MessageEvent<{ pcm: ArrayBuffer; level: number }>) => {
    onChunk(event.data.pcm);
    onLevel(event.data.level);
  };
  source.connect(recorder);

  return {
    stop: async () => {
      recorder.port.onmessage = null;
      source.disconnect();
      recorder.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      await context.close();
      onLevel(0);
    },
  };
}
