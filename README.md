@'

\# slither-bot



Chrome MV3 extension plus Python native messaging backend for a Slither.io bot system.



Phase 1 goal: prove the data/control pipeline only.



No real strategy is implemented yet.



\## Current Phase 1 target



Phase 1 is complete only when:



1\. Chrome extension loads.

2\. Slither.io opens.

3\. `inject.js` finds game state globals.

4\. State streams from page to Python at about 33Hz.

5\. Python validates self position, angle, speed, mass, snakes, and food.

6\. Python sends a dummy steering command.

7\. The page applies the command.

8\. Command acknowledgement latency is logged.



\## Repo layout



```text

slither-bot/

├── extension/

│   ├── manifest.json

│   ├── content.js

│   ├── inject.js

│   └── background.js

├── bot/

│   ├── bot\_bridge.py

│   ├── strategy.py

│   ├── perception.py

│   ├── geometry.py

│   └── config.py

├── tools/

│   ├── lag\_experiments.py

│   └── state\_logger.py

├── tests/

│   └── test\_geometry.py

├── requirements.txt

├── pytest.ini

├── README.md

└── .github/

&#x20;   └── workflows/

&#x20;       └── test.yml

