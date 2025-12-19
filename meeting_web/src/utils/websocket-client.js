/**
 * WebSocketClient
 * Handles connection to backend and message processing.
 */
export class WebSocketClient {
    constructor(url, onMessage, onOpen, onClose, onError) {
        this.url = url;
        this.onMessage = onMessage;
        this.onOpen = onOpen;
        this.onClose = onClose;
        this.onError = onError;
        this.ws = null;
    }

    connect(meetingId, options = {}) {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log("WS Connected");
            // Send handshake
            const handshake = {
                meeting_id: meetingId,
                sample_rate: 16000,
                use_cloud_asr: options.useCloudAsr || false
            };
            this.ws.send(JSON.stringify(handshake));
            if (this.onOpen) this.onOpen();
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (this.onMessage) this.onMessage(data);
            } catch (e) {
                console.error("Error parsing WS message:", e);
            }
        };

        this.ws.onclose = (event) => {
            console.log("WS Closed:", event.code, event.reason);
            if (this.onClose) this.onClose(event);
        };

        this.ws.onerror = (error) => {
            console.error("WS Error:", error);
            if (this.onError) this.onError(error);
        };
    }

    sendAudio(chunk) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(chunk);
        }
    }

    sendStop() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: "stop" }));
        }
    }



  close() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}
