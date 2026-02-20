import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Phone, PhoneOff, Mic } from 'lucide-react';
import { useStore } from '../store';

const CAPTURE_SAMPLE_RATE = 16000;
const PLAYBACK_SAMPLE_RATE = 24000;

const CallArea = () => {
    const {
        callActive, callState, callTranscript, callResponseText,
        callMessages, callError,
        startCall, endCall, interruptCall, sendCallAudio, sendVadSpeechEnd,
        addCallAudioListener, removeCallAudioListener,
        currentWorkspace, currentThread,
    } = useStore();

    const [isPttHeld, setIsPttHeld] = useState(false);

    // Audio capture refs
    const mediaStreamRef = useRef(null);
    const audioCtxRef = useRef(null);
    const processorRef = useRef(null);
    const isPttHeldRef = useRef(false);

    // Playback refs
    const playbackCtxRef = useRef(null);
    const nextPlayTimeRef = useRef(0);
    // When true, incoming audio blobs are silently dropped (interrupt in flight)
    const mutePlaybackRef = useRef(false);

    const scrollRef = useRef(null);

    // Keep ref in sync
    useEffect(() => { isPttHeldRef.current = isPttHeld; }, [isPttHeld]);

    // Auto-scroll conversation
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [callMessages, callResponseText, callTranscript]);

    // --- Audio Playback ---

    // Nuclear kill: close the entire AudioContext so all queued audio dies instantly,
    // then create a fresh one for the next round of playback.
    const killPlayback = useCallback(() => {
        mutePlaybackRef.current = true;
        if (playbackCtxRef.current && playbackCtxRef.current.state !== 'closed') {
            playbackCtxRef.current.close().catch(() => {});
        }
        playbackCtxRef.current = null;
        nextPlayTimeRef.current = 0;
    }, []);

    const ensurePlaybackCtx = useCallback(() => {
        if (!playbackCtxRef.current || playbackCtxRef.current.state === 'closed') {
            playbackCtxRef.current = new AudioContext({ sampleRate: PLAYBACK_SAMPLE_RATE });
            nextPlayTimeRef.current = 0;
        }
        return playbackCtxRef.current;
    }, []);

    const handleAudioBlob = useCallback(async (blob) => {
        // Drop audio that arrives after an interrupt but before the backend caught up
        if (mutePlaybackRef.current) return;

        const ctx = ensurePlaybackCtx();
        const arrayBuf = await blob.arrayBuffer();
        const int16 = new Int16Array(arrayBuf);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768;
        }

        const audioBuffer = ctx.createBuffer(1, float32.length, PLAYBACK_SAMPLE_RATE);
        audioBuffer.getChannelData(0).set(float32);

        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);

        // Schedule gapless playback
        const now = ctx.currentTime;
        const startTime = Math.max(now, nextPlayTimeRef.current);
        source.start(startTime);
        nextPlayTimeRef.current = startTime + audioBuffer.duration;
    }, [ensurePlaybackCtx]);

    // Register/unregister audio listener
    useEffect(() => {
        addCallAudioListener(handleAudioBlob);
        return () => removeCallAudioListener(handleAudioBlob);
    }, [handleAudioBlob, addCallAudioListener, removeCallAudioListener]);

    // When backend transitions to "listening", un-mute playback so next response is heard
    useEffect(() => {
        if (callState === 'speaking') {
            mutePlaybackRef.current = false;
        }
    }, [callState]);

    // --- Mic Capture ---
    const startMic = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: CAPTURE_SAMPLE_RATE,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            mediaStreamRef.current = stream;

            const ctx = new AudioContext({ sampleRate: CAPTURE_SAMPLE_RATE });
            audioCtxRef.current = ctx;
            const source = ctx.createMediaStreamSource(stream);

            const processor = ctx.createScriptProcessor(4096, 1, 1);
            processorRef.current = processor;

            processor.onaudioprocess = (e) => {
                if (!isPttHeldRef.current) return;

                const input = e.inputBuffer.getChannelData(0);
                const pcm = new Int16Array(input.length);
                for (let i = 0; i < input.length; i++) {
                    pcm[i] = Math.max(-32768, Math.min(32767, input[i] * 32768));
                }
                sendCallAudio(pcm.buffer);
            };

            source.connect(processor);
            processor.connect(ctx.destination);
        } catch (err) {
            console.error('Mic access error:', err);
        }
    }, [sendCallAudio]);

    const stopMic = useCallback(() => {
        if (processorRef.current) processorRef.current.disconnect();
        if (audioCtxRef.current) audioCtxRef.current.close();
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach(t => t.stop());
        }
        mediaStreamRef.current = null;
        audioCtxRef.current = null;
        processorRef.current = null;
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopMic();
            killPlayback();
        };
    }, [stopMic, killPlayback]);

    // --- Call Handlers ---
    const handleStartCall = async () => {
        mutePlaybackRef.current = false;
        ensurePlaybackCtx();
        startCall();
        await startMic();
    };

    const handleEndCall = () => {
        killPlayback();
        stopMic();
        endCall();
    };

    const handlePttDown = () => {
        // Always kill local audio playback (covers queued audio after backend finished)
        killPlayback();
        // If backend is still generating, send interrupt to cancel LLM/TTS
        if (callState === 'speaking' || callState === 'thinking') {
            interruptCall();
        }
        setIsPttHeld(true);
    };

    const handlePttUp = () => {
        setIsPttHeld(false);
        sendVadSpeechEnd();
    };

    // --- State indicator ---
    const stateConfig = {
        idle: { color: 'bg-gray-700', ring: '', label: 'Ready' },
        connecting: { color: 'bg-yellow-500', ring: 'animate-pulse', label: 'Connecting...' },
        listening: { color: 'bg-green-500', ring: 'animate-pulse', label: 'Listening...' },
        thinking: { color: 'bg-blue-500', ring: 'animate-pulse', label: 'Thinking...' },
        speaking: { color: 'bg-purple-500', ring: 'animate-pulse', label: 'Speaking...' },
    };
    const sc = stateConfig[callState] || stateConfig.idle;

    const canStart = currentWorkspace && currentThread && !callActive;

    return (
        <div className="flex flex-col items-center h-full bg-[var(--bg-primary)] text-[var(--text-primary)] p-6 overflow-hidden">

            {/* State Indicator */}
            <div className="flex flex-col items-center gap-4 mt-8">
                <div className={`w-28 h-28 rounded-full ${sc.color} ${sc.ring} flex items-center justify-center shadow-lg transition-colors duration-300`}>
                    <Phone size={44} className="text-white" />
                </div>
                <span className="text-base font-medium text-[var(--text-secondary)]">{sc.label}</span>
            </div>

            {/* Live Transcript */}
            {callTranscript && (
                <div className="mt-3 text-sm italic text-[var(--text-muted)] max-w-lg text-center">
                    &ldquo;{callTranscript}&rdquo;
                </div>
            )}

            {/* Streaming Response */}
            {callResponseText && (
                <div className="mt-2 text-sm text-blue-300 max-w-lg text-center leading-relaxed">
                    {callResponseText}
                </div>
            )}

            {/* Error */}
            {callError && (
                <div className="mt-2 text-sm text-red-400">{callError}</div>
            )}

            {/* Conversation History */}
            <div ref={scrollRef} className="flex-1 w-full max-w-xl mt-6 overflow-y-auto space-y-2 px-2 min-h-0">
                {callMessages.map((m, i) => (
                    <div key={i} className={`text-sm px-3 py-2 rounded-lg ${
                        m.role === 'user'
                            ? 'bg-green-900/30 text-green-300 ml-12'
                            : 'bg-gray-800 text-gray-300 mr-12'
                    }`}>
                        {m.content}
                    </div>
                ))}
            </div>

            {/* Controls */}
            <div className="flex items-center gap-4 mt-4 mb-4">
                {!callActive ? (
                    <button
                        onClick={handleStartCall}
                        disabled={!canStart}
                        className={`flex items-center gap-2 px-8 py-3 rounded-full text-lg font-medium transition-colors ${
                            canStart
                                ? 'bg-green-600 hover:bg-green-500 text-white cursor-pointer'
                                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                        }`}
                    >
                        <Phone size={22} /> Start Call
                    </button>
                ) : (
                    <>
                        {/* Push-to-talk */}
                        <button
                            onMouseDown={handlePttDown}
                            onMouseUp={handlePttUp}
                            onMouseLeave={handlePttUp}
                            onTouchStart={handlePttDown}
                            onTouchEnd={handlePttUp}
                            className={`flex items-center gap-2 px-8 py-4 rounded-full text-base font-medium transition-colors select-none ${
                                isPttHeld
                                    ? 'bg-green-500 text-white shadow-lg shadow-green-500/30'
                                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                            }`}
                        >
                            <Mic size={22} />
                            {isPttHeld ? 'Recording...' : 'Hold to Talk'}
                        </button>

                        {/* End Call */}
                        <button
                            onClick={handleEndCall}
                            className="flex items-center gap-2 px-8 py-3 rounded-full bg-red-600 hover:bg-red-500 text-white text-lg font-medium transition-colors"
                        >
                            <PhoneOff size={22} /> End Call
                        </button>
                    </>
                )}
            </div>

            {!currentWorkspace && (
                <p className="text-sm text-[var(--text-muted)] mt-2">Select a workspace to start a call.</p>
            )}
            {currentWorkspace && !currentThread && (
                <p className="text-sm text-[var(--text-muted)] mt-2">Select or create a thread to start a call.</p>
            )}
        </div>
    );
};

export default CallArea;
