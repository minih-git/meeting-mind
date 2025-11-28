/**
 * AudioProcessor
 * Handles microphone access, downsampling, and conversion to PCM 16k 16bit.
 */
export class AudioProcessor {
    constructor(onAudioData) {
        this.onAudioData = onAudioData;
        this.audioContext = null;
        this.processor = null;
        this.stream = null;
        this.stream = null;
        this.targetSampleRate = 16000;
        this.analyser = null;
    }

    getAnalyser() {
        return this.analyser;
    }

    async setupPlayback(arrayBuffer) {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.targetSampleRate
            });
        }

        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;

        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;

        source.connect(this.analyser);
        this.analyser.connect(this.audioContext.destination);

        source.start(0);
        
        return { 
            analyser: this.analyser, 
            source: source,
            duration: audioBuffer.duration 
        };
    }

    async start() {
        try {
            const constraints = {
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            };
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Try to use native 16kHz context for better resampling quality
            try {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            } catch (e) {
                console.warn("16kHz AudioContext not supported, falling back to default.", e);
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            const source = this.audioContext.createMediaStreamSource(this.stream);
            
            // Create Analyser
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            
            // Use ScriptProcessor
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
            
            this.processor.onaudioprocess = (e) => {
                const inputData = e.inputBuffer.getChannelData(0);
                this.processAudio(inputData, this.audioContext.sampleRate);
            };

            source.connect(this.analyser);
            this.analyser.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            
            console.log(`AudioProcessor started. Input rate: ${this.audioContext.sampleRate}, Target: ${this.targetSampleRate}`);
        } catch (err) {
            console.error("Error accessing microphone:", err);
            throw err;
        }
    }

    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        console.log("AudioProcessor stopped.");
    }

    processAudio(inputData, inputSampleRate) {
        // Calculate RMS
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);
        if (Math.random() < 0.05) {
            console.log(`Audio Input RMS: ${rms.toFixed(4)}, Rate: ${inputSampleRate}`);
        }

        let result;
        
        // If sample rate is close to target (within 100Hz), skip resampling
        if (Math.abs(inputSampleRate - this.targetSampleRate) < 100) {
            result = inputData;
        } else {
            // Downsample
            const ratio = inputSampleRate / this.targetSampleRate;
            const newLength = Math.floor(inputData.length / ratio);
            result = new Float32Array(newLength);
            
            for (let i = 0; i < newLength; i++) {
                const offset = i * ratio;
                const index = Math.floor(offset);
                const nextIndex = Math.min(index + 1, inputData.length - 1);
                const fraction = offset - index;
                result[i] = inputData[index] * (1 - fraction) + inputData[nextIndex] * fraction;
            }
        }

        // Convert to Int16 PCM with Gain
        const gain = 5.0; // Reduced to avoid clipping
        const pcmData = new Int16Array(result.length);
        for (let i = 0; i < result.length; i++) {
            let s = result[i] * gain;
            s = Math.max(-1, Math.min(1, s));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Send raw bytes
        this.onAudioData(pcmData.buffer);
    }

    /**
     * Process an audio file: Decode -> Resample -> Convert to PCM Int16
     * @param {File} file 
     * @returns {Promise<ArrayBuffer>}
     */
    static async processAudioFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = async (e) => {
                try {
                    const arrayBuffer = e.target.result;
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                    
                    // Decode audio data (this handles mp3, wav, etc.)
                    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                    
                    // Create analyser for file playback visualization if needed
                    // Note: This static method just processes data, it doesn't play it back in real-time usually.
                    // If we want visualization for file upload, we might need to change how we handle file upload.
                    // For now, let's keep it simple and only visualize mic input, 
                    // OR we can return the audioContext/analyser if we were playing it.
                    // But here we are just processing offline.
                    
                    const offlineCtx = new OfflineAudioContext(1, audioBuffer.duration * 16000, 16000);
                    const source = offlineCtx.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(offlineCtx.destination);
                    source.start();
                    
                    const renderedBuffer = await offlineCtx.startRendering();
                    const channelData = renderedBuffer.getChannelData(0);
                    
                    // Convert to Int16 PCM
                    const pcmData = new Int16Array(channelData.length);
                    for (let i = 0; i < channelData.length; i++) {
                        let s = channelData[i];
                        s = Math.max(-1, Math.min(1, s));
                        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    }
                    
                    resolve(pcmData.buffer);
                } catch (err) {
                    reject(err);
                }
            };
            reader.onerror = reject;
            reader.readAsArrayBuffer(file);
        });
    }
}
