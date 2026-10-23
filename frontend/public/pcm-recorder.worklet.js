// Audio thread: resamples mic input to 16 kHz mono PCM16 and posts 100 ms chunks.
const TARGET_RATE = 16000;
const CHUNK_SAMPLES = TARGET_RATE / 10;

class PcmRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / TARGET_RATE; // `sampleRate` is an AudioWorkletGlobalScope global
    this.position = 0; // fractional, carried across 128-sample blocks
    this.chunk = new Int16Array(CHUNK_SAMPLES);
    this.filled = 0;
    this.peak = 0;
  }

  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;

    while (this.position < input.length) {
      // Box-filter average over the source window limits aliasing.
      const start = Math.floor(this.position);
      const end = Math.min(input.length, Math.floor(this.position + this.ratio));
      let sum = 0;
      for (let i = start; i < Math.max(end, start + 1); i++) sum += input[i];
      const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));

      this.peak = Math.max(this.peak, Math.abs(sample));
      this.chunk[this.filled++] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      if (this.filled === CHUNK_SAMPLES) {
        this.port.postMessage({ pcm: this.chunk.buffer, level: this.peak }, [this.chunk.buffer]);
        this.chunk = new Int16Array(CHUNK_SAMPLES);
        this.filled = 0;
        this.peak = 0;
      }
      this.position += this.ratio;
    }
    this.position -= input.length;
    return true;
  }
}

registerProcessor("pcm-recorder", PcmRecorderProcessor);
