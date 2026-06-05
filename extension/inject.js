(() => {
  "use strict";

  const INJECT_SOURCE = "slither-bot-inject";
  const CONTENT_SOURCE = "slither-bot-content";

  const TICK_INTERVAL_MS = 30;
  const DISCOVERY_INTERVAL_MS = 1000;

  const MAX_SNAKES = 200;
  const MAX_FOOD = 1500;
  const MAX_POINTS_PER_SNAKE = 500;

  const TWO_PI = Math.PI * 2;

  let sequence = 0;
  let lastDiscoveryAt = 0;
  let cachedSelfRef = null;
  let cachedSnakesRef = null;
  let cachedFoodRef = null;
  let lastState = null;
  let lastCommand = null;
  let lastStatus = null;

  function log(...args) {
    console.log("[slither-bot/inject]", ...args);
  }

  function warn(...args) {
    console.warn("[slither-bot/inject]", ...args);
  }

  function now() {
    return performance.now();
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function firstNumber(object, keys, fallback = 0) {
    if (!object || typeof object !== "object") {
      return fallback;
    }

    for (const key of keys) {
      const value = object[key];
      if (isFiniteNumber(value)) {
        return value;
      }
    }

    return fallback;
  }

  function normalizeAngleRadians(angle) {
    if (!isFiniteNumber(angle)) {
      return 0;
    }

    let result = angle % TWO_PI;
    if (result < 0) {
      result += TWO_PI;
    }
    return result;
  }

  function encodeAngle8(angle) {
    const normalized = normalizeAngleRadians(angle);
    return Math.floor((normalized / TWO_PI) * 256) & 255;
  }

  function postToContent(type, payloadKey, payload) {
    window.postMessage(
      {
        source: INJECT_SOURCE,
        type,
        [payloadKey]: payload
      },
      "*"
    );
  }

  function postStatus(status) {
    lastStatus = {
      ...status,
      ts: now()
    };

    postToContent("INJECT_STATUS", "status", lastStatus);
  }

  function looksLikeSelfSnake(candidate) {
    if (!candidate || typeof candidate !== "object") {
      return false;
    }

    const x = firstNumber(candidate, ["x", "xx"], NaN);
    const y = firstNumber(candidate, ["y", "yy"], NaN);
    const angle = firstNumber(candidate, ["ang", "eang", "wang"], NaN);
    const speed = firstNumber(candidate, ["sp", "spd"], NaN);

    return (
      isFiniteNumber(x) &&
      isFiniteNumber(y) &&
      isFiniteNumber(angle) &&
      isFiniteNumber(speed)
    );
  }

  function looksLikeEnemySnake(candidate) {
    if (!candidate || typeof candidate !== "object") {
      return false;
    }

    const x = firstNumber(candidate, ["xx", "x"], NaN);
    const y = firstNumber(candidate, ["yy", "y"], NaN);
    const angle = firstNumber(candidate, ["ang", "eang", "wang"], NaN);
    const speed = firstNumber(candidate, ["sp", "spd"], NaN);

    return (
      isFiniteNumber(x) &&
      isFiniteNumber(y) &&
      isFiniteNumber(angle) &&
      isFiniteNumber(speed)
    );
  }

  function looksLikeFood(candidate) {
    if (!candidate || typeof candidate !== "object") {
      return false;
    }

    const x = firstNumber(candidate, ["x", "xx"], NaN);
    const y = firstNumber(candidate, ["y", "yy"], NaN);
    const size = firstNumber(candidate, ["sz", "rad", "gr"], NaN);

    return isFiniteNumber(x) && isFiniteNumber(y) && isFiniteNumber(size);
  }

  function discoverSnakes() {
    const directCandidates = [
      window.snakes,
      window.larva,
      window.slithers,
      window.players
    ];

    for (const candidate of directCandidates) {
      if (Array.isArray(candidate)) {
        const found = candidate.some(looksLikeEnemySnake);
        if (found) {
          return candidate;
        }
      }
    }

    return null;
  }

  function discoverSelf() {
    const directCandidates = [
      window.snake,
      window.slither,
      window.player,
      window.mySnake
    ];

    for (const candidate of directCandidates) {
      if (looksLikeSelfSnake(candidate)) {
        return candidate;
      }
    }

    const snakes = discoverSnakes();

    if (Array.isArray(snakes)) {
      for (const snake of snakes) {
        if (snake && snake === window.snake && looksLikeSelfSnake(snake)) {
          return snake;
        }
      }

      for (const snake of snakes) {
        if (snake && snake.id === window.snake_id && looksLikeSelfSnake(snake)) {
          return snake;
        }
      }
    }

    return null;
  }

  function discoverFood() {
    const directCandidates = [
      window.foods,
      window.food,
      window.fooda,
      window.preys
    ];

    for (const candidate of directCandidates) {
      if (Array.isArray(candidate)) {
        const found = candidate.some(looksLikeFood);
        if (found) {
          return candidate;
        }
      }
    }

    return null;
  }

  function refreshDiscovery(force = false) {
    const current = now();

    if (!force && current - lastDiscoveryAt < DISCOVERY_INTERVAL_MS) {
      return;
    }

    lastDiscoveryAt = current;

    cachedSelfRef = discoverSelf();
    cachedSnakesRef = discoverSnakes();
    cachedFoodRef = discoverFood();

    postStatus({
      discoveredSelf: Boolean(cachedSelfRef),
      discoveredSnakes: Array.isArray(cachedSnakesRef),
      discoveredFood: Array.isArray(cachedFoodRef),
      snakeCount: Array.isArray(cachedSnakesRef) ? cachedSnakesRef.length : 0,
      foodCount: Array.isArray(cachedFoodRef) ? cachedFoodRef.length : 0
    });
  }

  function normalizePoint(point) {
    if (!point) {
      return null;
    }

    if (Array.isArray(point) && point.length >= 2) {
      const x = Number(point[0]);
      const y = Number(point[1]);

      if (Number.isFinite(x) && Number.isFinite(y)) {
        return [x, y];
      }

      return null;
    }

    if (typeof point === "object") {
      const x = firstNumber(point, ["x", "xx", "fx"], NaN);
      const y = firstNumber(point, ["y", "yy", "fy"], NaN);

      if (isFiniteNumber(x) && isFiniteNumber(y)) {
        return [x, y];
      }
    }

    return null;
  }

  function normalizePoints(points) {
    if (!Array.isArray(points)) {
      return [];
    }

    const result = [];
    const limit = Math.min(points.length, MAX_POINTS_PER_SNAKE);

    for (let i = 0; i < limit; i += 1) {
      const point = normalizePoint(points[i]);
      if (point) {
        result.push(point);
      }
    }

    return result;
  }

  function normalizeSelf(snake) {
    if (!snake || typeof snake !== "object") {
      return null;
    }

    const x = firstNumber(snake, ["x", "xx"], NaN);
    const y = firstNumber(snake, ["y", "yy"], NaN);
    const ang = firstNumber(snake, ["ang", "eang", "wang"], NaN);
    const sp = firstNumber(snake, ["sp", "spd"], NaN);
    const fam = firstNumber(snake, ["fam", "sc", "sct"], 1);

    if (!isFiniteNumber(x) || !isFiniteNumber(y)) {
      return null;
    }

    return {
      x,
      y,
      ang: normalizeAngleRadians(ang),
      sp,
      fam,
      pts: normalizePoints(snake.pts)
    };
  }

  function normalizeSnake(snake, index) {
    if (!snake || typeof snake !== "object") {
      return null;
    }

    const xx = firstNumber(snake, ["xx", "x"], NaN);
    const yy = firstNumber(snake, ["yy", "y"], NaN);
    const ang = firstNumber(snake, ["ang", "eang", "wang"], NaN);
    const sp = firstNumber(snake, ["sp", "spd"], NaN);
    const sc = firstNumber(snake, ["sc", "fam", "sct"], 1);

    if (!isFiniteNumber(xx) || !isFiniteNumber(yy)) {
      return null;
    }

    const rawId = snake.id ?? snake.sid ?? snake.snake_id ?? index;
    const idNumber = Number(rawId);
    const id = Number.isFinite(idNumber) ? idNumber : index;

    return {
      id,
      xx,
      yy,
      ang: normalizeAngleRadians(ang),
      sp,
      sc,
      pts: normalizePoints(snake.pts)
    };
  }

  function normalizeFood(food) {
    if (!food || typeof food !== "object") {
      return null;
    }

    const x = firstNumber(food, ["x", "xx"], NaN);
    const y = firstNumber(food, ["y", "yy"], NaN);
    const sz = firstNumber(food, ["sz", "rad", "gr"], 1);

    if (!isFiniteNumber(x) || !isFiniteNumber(y)) {
      return null;
    }

    return {
      x,
      y,
      sz
    };
  }

  function captureState() {
    refreshDiscovery(false);

    if (!cachedSelfRef) {
      refreshDiscovery(true);
    }

    const self = normalizeSelf(cachedSelfRef);

    if (!self) {
      return null;
    }

    const snakes = [];

    if (Array.isArray(cachedSnakesRef)) {
      const limit = Math.min(cachedSnakesRef.length, MAX_SNAKES);

      for (let i = 0; i < limit; i += 1) {
        const rawSnake = cachedSnakesRef[i];

        if (!rawSnake || rawSnake === cachedSelfRef) {
          continue;
        }

        const snake = normalizeSnake(rawSnake, i);

        if (snake) {
          snakes.push(snake);
        }
      }
    }

    const food = [];

    if (Array.isArray(cachedFoodRef)) {
      const limit = Math.min(cachedFoodRef.length, MAX_FOOD);

      for (let i = 0; i < limit; i += 1) {
        const item = normalizeFood(cachedFoodRef[i]);

        if (item) {
          food.push(item);
        }
      }
    }

    return {
      self,
      snakes,
      food,
      ts: now()
    };
  }

  function applyMouseSteering(angle) {
    const distance = 10000;
    window.xm = Math.cos(angle) * distance;
    window.ym = Math.sin(angle) * distance;
  }

  function applyBoost(boost) {
    const enabled = Boolean(boost);

    if (typeof window.setAcceleration === "function") {
      try {
        window.setAcceleration(enabled ? 1 : 0);
        return;
      } catch (error) {
        warn("setAcceleration failed", error);
      }
    }

    window.want_e = enabled ? 1 : 0;
    window.isboost = enabled ? 1 : 0;
    window.boosting = enabled ? 1 : 0;
  }

  function applyCommand(command) {
    if (!command || typeof command !== "object") {
      return;
    }

    const angle = Number(command.angle);
    const boost = Boolean(command.boost);

    if (!Number.isFinite(angle)) {
      return;
    }

    const normalizedAngle = normalizeAngleRadians(angle);

    applyMouseSteering(normalizedAngle);
    applyBoost(boost);

    lastCommand = {
      angle: normalizedAngle,
      angle8: encodeAngle8(normalizedAngle),
      boost,
      seq: command.seq ?? null,
      state_ts: command.state_ts ?? null,
      received_ts: now()
    };

    let commandLatencyMs = null;

    if (Number.isFinite(Number(command.state_ts))) {
      commandLatencyMs = now() - Number(command.state_ts);
    }

    postToContent("ACK", "ack", {
      seq: command.seq ?? null,
      state_ts: command.state_ts ?? null,
      angle: normalizedAngle,
      angle8: encodeAngle8(normalizedAngle),
      boost,
      inject_received_ts: now(),
      command_latency_ms: commandLatencyMs
    });
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) {
      return;
    }

    const message = event.data;

    if (!message || typeof message !== "object") {
      return;
    }

    if (message.source !== CONTENT_SOURCE) {
      return;
    }

    if (message.type === "COMMAND") {
      applyCommand(message.command);
    }
  });

  function tick() {
    try {
      const state = captureState();

      if (state) {
        sequence += 1;
        state.seq = sequence;
        lastState = state;

        postToContent("STATE", "state", state);
      }
    } catch (error) {
      warn("state capture failed", error);

      postStatus({
        error: String(error && error.message ? error.message : error)
      });
    }
  }

  window.__SLITHER_BOT_PHASE1__ = {
    captureState,
    refreshDiscovery,
    applyCommand,
    getLastState: () => lastState,
    getLastCommand: () => lastCommand,
    getLastStatus: () => lastStatus
  };

  refreshDiscovery(true);
  setInterval(tick, TICK_INTERVAL_MS);

  log("Phase 1 injector active");
})();
