import React, { useEffect, useRef } from 'react';

const ParticleBackground = ({ analyser, theme }) => {
  const canvasRef = useRef(null);
  const particles = useRef([]);
  const animationRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let width = window.innerWidth;
    let height = window.innerHeight;

    canvas.width = width;
    canvas.height = height;

    // Initialize particles
    const particleCount = 60;
    for (let i = 0; i < particleCount; i++) {
      particles.current.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 2,
        vy: (Math.random() - 0.5) * 2,
        size: Math.random() * 3 + 1,
        baseSize: Math.random() * 3 + 1,
        color: theme === 'light' 
            ? `rgba(${Math.random() * 100}, ${Math.random() * 100 + 50}, 200, 0.5)` // Darker/Blueish for light theme
            : `rgba(${Math.random() * 100 + 100}, ${Math.random() * 100 + 150}, 255, 0.5)` // Lighter for dark theme
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      
      // Get audio data if analyser is present
      let audioData = new Uint8Array(0);
      let average = 0;
      if (analyser) {
        audioData = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(audioData);
        const sum = audioData.reduce((a, b) => a + b, 0);
        average = sum / audioData.length;
      }

      // Update and draw particles
      particles.current.forEach((p, i) => {
        // Audio reactivity
        let scale = 1;
        if (analyser) {
            // Map particle index to frequency bin roughly
            const binIndex = Math.floor((i / particleCount) * audioData.length);
            const val = audioData[binIndex] || 0;
            scale = 1 + (val / 255) * 2; // Scale up to 3x
            
            // Add some velocity based on overall energy
            p.x += p.vx * (1 + average / 50);
            p.y += p.vy * (1 + average / 50);
        } else {
            p.x += p.vx;
            p.y += p.vy;
        }

        // Boundary check
        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        // Draw
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.baseSize * scale, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.fill();
        
        // Connections
        particles.current.forEach((p2, j) => {
            if (i === j) return;
            const dx = p.x - p2.x;
            const dy = p.y - p2.y;
            const distSq = dx * dx + dy * dy;
            
            if (distSq < 10000) { // 100 * 100
                ctx.beginPath();
                ctx.strokeStyle = theme === 'light'
                    ? `rgba(100, 150, 255, ${0.1 * (1 - Math.sqrt(distSq) / 100)})`
                    : `rgba(150, 200, 255, ${0.1 * (1 - Math.sqrt(distSq) / 100)})`;
                ctx.lineWidth = 0.5;
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();
            }
        });
      });

      animationRef.current = requestAnimationFrame(render);
    };

    render();

    const handleResize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width;
      canvas.height = height;
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationRef.current);
    };
  }, [analyser, theme]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: 0,
        background: theme === 'light' 
            ? 'linear-gradient(135deg, #fdfbf7 0%, #e8eaf6 100%)' 
            : 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)'
      }}
    />
  );
};

export default React.memo(ParticleBackground);
