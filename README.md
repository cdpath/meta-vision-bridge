# meta-vision-bridge

tldr:

```mermaid
sequenceDiagram
    participant MG as Meta Glass
    participant TW as Twilio WhatsApp
    participant T as Twilio
    participant WS as Webhook SVC
    participant CGP as ChatGPT

    Note over MG,T: Setup Phase
    MG->>MG: Bind WhatsApp account
    T->>T: Configure webhook to Webhook SVC

    Note over MG,CGP: Main Flow
    MG->>TW: Send text/image
    TW->>T: Forward message
    T->>WS: Send to webhook
    WS->>CGP: Request response
    CGP->>WS: Provide response
    WS->>T: Send reply
    T->>TW: Forward reply
    TW->>MG: Deliver reply
```

prerequisite:

- whatsapp account
- Twilio account
- VPS with public IP
