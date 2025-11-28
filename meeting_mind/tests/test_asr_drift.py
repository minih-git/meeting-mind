import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os

# Mock settings before importing asr_engine
with patch.dict(sys.modules, {'meeting_mind.app.core.config': MagicMock()}):
    from meeting_mind.app.services.asr_engine import ASREngine

class TestASRBuffer(unittest.TestCase):
    def setUp(self):
        self.engine = ASREngine()
        # Mock models
        self.engine.asr_model = MagicMock()
        self.engine.vad_model = MagicMock()
        self.engine.punc_model = MagicMock()
        self.engine.speaker_model = MagicMock()
        
        # Mock speaker registry
        self.engine.speaker_registry = {}

    def test_long_running_buffer_drift(self):
        session_id = "test_session"
        
        # Simulate 1 second of audio (16000 samples * 2 bytes)
        chunk_size = 32000 
        audio_chunk = b'\x00' * chunk_size
        
        # Mock VAD to return a segment every 1 second
        # VAD input is float32, so we need to handle that if we mock generate
        
        # We want to simulate a scenario where we process many chunks
        # and ensure buffer_offset_bytes tracks correctly.
        
        # Let's simulate 100 iterations.
        # In the old code, integer division 32000 // 32 = 1000 ms.
        # But if we had chunks that weren't perfectly divisible or if VAD returned 
        # timestamps that caused non-aligned cuts, we might see drift.
        
        # Actually, the issue described was "fragment exceeds buffer range".
        # This happens when (start_ms - buffer_offset_ms) * 32 > current_buffer_len
        # OR when we calculate start_byte and it's wrong.
        
        # Let's try to feed chunks of size 320 (10ms) to trigger frequent updates
        # and see if we can break it with the old logic (mental check) or pass with new.
        
        chunk_size = 320 # 10ms
        audio_chunk = b'\x00' * chunk_size
        
        # Mock VAD to return a segment from 0 to 10ms every time? 
        # No, VAD returns absolute timestamps.
        
        current_time_ms = 0
        
        for i in range(1000): # Run for 10 seconds
            # Mock VAD response
            # VAD receives the *new* chunk.
            # But the engine maintains state.
            
            # Let's say VAD detects speech from current_time_ms to current_time_ms + 10
            start_ms = current_time_ms
            end_ms = current_time_ms + 10
            
            self.engine.vad_model.generate.return_value = [{"value": [[start_ms, end_ms]]}]
            
            # Mock ASR response
            self.engine.asr_model.generate.return_value = [{"text": "test"}]
            
            # Run inference
            try:
                self.engine.inference_stream(session_id, audio_chunk)
            except Exception as e:
                self.fail(f"Inference failed at iteration {i}: {e}")
            
            current_time_ms += 10
            
            # Check internal state
            cache = self.engine.cache[session_id]
            # Buffer should be empty or near empty if we consumed everything
            # With 10ms chunks and 10ms segments, we consume everything.
            
            # Verify offset
            expected_offset = (i + 1) * 320
            self.assertEqual(cache["buffer_offset_bytes"], expected_offset, 
                             f"Offset mismatch at iteration {i}")
            self.assertEqual(len(cache["audio_buffer"]), 0, 
                             f"Buffer not empty at iteration {i}")

    def test_vad_tolerance(self):
        """Test that small VAD timestamp overflows are handled gracefully."""
        session_id = "test_tolerance"
        
        # 300ms of audio (9600 bytes)
        # We need > 200ms to pass the min duration check in asr_engine
        chunk_size = 9600
        audio_chunk = b'\x00' * chunk_size
        
        # VAD says speech ends at 301ms (9632 bytes)
        # This is 32 bytes (1ms) more than we have.
        start_ms = 0
        end_ms = 301
        
        self.engine.vad_model.generate.return_value = [{"value": [[start_ms, end_ms]]}]
        self.engine.asr_model.generate.return_value = [{"text": "tolerance test"}]
        
        # Run inference
        results = self.engine.inference_stream(session_id, audio_chunk)
        
        # Should produce a result despite the overflow
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "tolerance test")
        
        # Buffer should be empty (consumed)
        cache = self.engine.cache[session_id]
        self.assertEqual(len(cache["audio_buffer"]), 0)
        # Offset should be updated by the clamped amount (9600 bytes)
        self.assertEqual(cache["buffer_offset_bytes"], 9600)

    def test_long_speech_force_split(self):
        """Test that long speech (>10s) is forcibly split."""
        session_id = "test_long_speech"
        
        # 11 seconds of audio (16000 * 2 * 11 = 352000 bytes)
        chunk_size = 352000
        audio_chunk = b'\x00' * chunk_size
        
        # VAD says speech started at 0 and hasn't ended (-1)
        start_ms = 0
        end_ms = -1
        
        self.engine.vad_model.generate.return_value = [{"value": [[start_ms, end_ms]]}]
        self.engine.asr_model.generate.return_value = [{"text": "long speech content"}]
        
        # Run inference
        results = self.engine.inference_stream(session_id, audio_chunk)
        
        # Should produce a result because of forced split
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "long speech content")
        
        # Check that the segment length is roughly 11s (since we process all available data)
        # In the implementation, we process everything if > 10s.
        # So timestamp should be around 11.0s
        self.assertAlmostEqual(results[0]["timestamp"], 11.0, delta=0.1)
        
        # Buffer should be empty
        cache = self.engine.cache[session_id]
        self.assertEqual(len(cache["audio_buffer"]), 0)
        
        # Next start time should be set to 11000ms
        self.assertEqual(cache["vad_state"]["current_start_ms"], 11000.0)

if __name__ == '__main__':
    unittest.main()
