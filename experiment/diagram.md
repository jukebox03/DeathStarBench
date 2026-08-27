 %% Frontend Core Request-Response Flow Diagram (Corrected)
    2 graph TD
    3     classDef main fill:#f9f,stroke:#333,stroke-width:4px,color:black;
    4     classDef worker fill:#ff9,stroke:#333,stroke-width:2px,color:black;
    5     classDef grpc fill:#9cf,stroke:#333,stroke-width:2px,color:black;
    6     classDef queue fill:#eee,stroke:#333,stroke-dasharray: 5 5,color:black;
    7
    8     subgraph "External"
    9         Client[🌍 External Client]
   10         Backend[🏭 Backend Service]
   11     end
   12
   13     subgraph "Frontend Process"
   14
   15         %% 1. Main Listener
   16         subgraph "1. Listener Group"
   17             Main["👮 Main / Listener<br>(http.ListenAndServe)"]:::main
   18         end
   19
   20         %% 2. Worker Group
   21         subgraph "2. Request Workers"
   22             Worker["👷 HTTP Worker<br>(Wait for Response)"]:::worker
   23         end
   24
   25         %% 3. gRPC Internal System
   26         subgraph "3. gRPC Internals (Hidden)"
   27             Queue[("📬 ControlBuffer<br>(Queue & Lock)")]:::queue
   28             Loopy["🚚 LoopyWriter<br>(Sender)"]:::grpc
   29             Reader["👀 TransportReader<br>(Receiver)"]:::grpc
   30         end
   31
   32     end
   33
   34     %% --- DATA FLOW STEPS ---
   35
   36     %% 1. Inbound
   37     Client -- "① TCP Connect" --> Main
   38     Main -- "② Spawn Worker" --> Worker
   39
   40     %% 2. Outbound Request (Sending)
   41     Worker -- "③ gRPC Call (SendMsg)" --> Queue
   42     Queue -- "④ Lock & Enqueue" --> Queue
   43     Queue -- "⑤ Dequeue" --> Loopy
   44     Loopy -- "⑥ Write Frame" --> Backend
   45
   46     %% 3. Inbound Response (Receiving)
   47     Backend -- "⑦ Response Frame" --> Reader
   48     Reader -- "⑧ Notify / Wake Up" --> Worker
   49
   50     %% 4. Final Response
   51     Worker -- "⑨ HTTP Response" --> Client
   52
   53     %% --- Styling ---
   54     linkStyle 2,3 stroke:red,stroke-width:2px;
   55     linkStyle 7 stroke:blue,stroke-width:3px;
   56     %% (Reader -> Worker 연결 강조)
   ```