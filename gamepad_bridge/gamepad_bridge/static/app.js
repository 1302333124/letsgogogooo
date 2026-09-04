const $ = (selector) => document.querySelector(selector);

function websocketUrl(role) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}/ws?role=${role}`;
}

function setConnection(state, text) {
  const element = $("#connection");
  if (!element) return;
  element.className = `status ${state}`;
  element.querySelector("span:last-child").textContent = text;
}

function renderInputs(gamepads, keyboard, target) {
  if (!gamepads.length && !keyboard.length) {
    target.innerHTML = '<div class="empty">浏览器尚未发现手柄输入</div>';
    return;
  }
  const gamepadHtml = gamepads.map((pad) => {
    const labels = controllerLabels(pad.id);
    const axes = pad.axes.map((value, index) => {
      const axisNames = ["左摇杆 X", "左摇杆 Y", "右摇杆 X", "右摇杆 Y"];
      const percent = Math.min(50, Math.abs(value) * 50);
      const left = value < 0 ? 50 - percent : 50;
      return `<div class="axis-row"><span title="轴 ${index}">${axisNames[index] || `轴 ${index}`}</span><div class="track"><span class="axis-fill" style="left:${left}%;width:${percent}%"></span></div><span class="value">${value.toFixed(2)}</span></div>`;
    }).join("");
    const extraButtons = pad.buttons.slice(17).map((button, offset) =>
      visualButton(pad, offset + 17, `B${offset + 17}`, `扩展按钮 ${offset + 17}`, "compact")
    ).join("");
    const mappingNote = pad.mapping === "standard" ? "标准映射" : "非标准映射，名称仅供参考";
    return `<article class="gamepad"><div class="gamepad-head"><span class="gamepad-name" title="${escapeHtml(pad.id)}">${escapeHtml(pad.id || "未知手柄")}</span><span class="gamepad-index">#${pad.index} · ${mappingNote}</span></div>${controllerDiagram(pad, labels)}<div class="section-label">摇杆原始数值</div><div class="axes">${axes || "无"}</div>${extraButtons ? `<div class="section-label">扩展按钮</div><div class="buttons">${extraButtons}</div>` : ""}</article>`;
  }).join("");
  const keyboardHtml = keyboard.length ? `<article class="gamepad"><div class="gamepad-head"><span class="gamepad-name">键盘模式手柄</span><span class="gamepad-index">兼容模式</span></div><div class="section-label">当前按键</div><div class="key-list">${keyboard.map((key) => `<span class="key-state">${escapeHtml(key.code)}</span>`).join("")}</div><p class="hint">该模式只能读取数字按键，无法获得模拟摇杆力度。</p></article>` : "";
  target.innerHTML = gamepadHtml + keyboardHtml;
}

function controllerLabels(id) {
  const name = String(id || "").toLowerCase();
  if (/playstation|dualshock|dualsense|sony|054c/.test(name)) {
    return {
      family: "PlayStation", face: ["×", "○", "□", "△"],
      faceNames: ["叉键", "圆圈键", "方块键", "三角键"],
      shoulders: ["L1", "R1", "L2", "R2"],
      center: ["Create", "Options", "PS"], sticks: ["L3", "R3"],
    };
  }
  if (/nintendo|switch|joy-con|057e/.test(name)) {
    return {
      family: "Nintendo", face: ["B", "A", "Y", "X"],
      faceNames: ["B 键", "A 键", "Y 键", "X 键"],
      shoulders: ["L", "R", "ZL", "ZR"],
      center: ["−", "+", "Home"], sticks: ["L Stick", "R Stick"],
    };
  }
  return {
    family: /xbox|xinput|microsoft|045e/.test(name) ? "Xbox" : "通用",
    face: ["A", "B", "X", "Y"],
    faceNames: ["A 键", "B 键", "X 键", "Y 键"],
    shoulders: ["LB", "RB", "LT", "RT"],
    center: ["View", "Menu", "Home"], sticks: ["LS", "RS"],
  };
}

function visualButton(pad, index, label, name, extraClass = "") {
  const button = pad.buttons[index] || { pressed: false, touched: false, value: 0 };
  const active = button.pressed || button.value > 0.05;
  return `<div class="pad-button ${active ? "pressed" : ""} ${extraClass}" title="${escapeHtml(name)} · 按钮 ${index} · ${button.value.toFixed(2)}"><span>${escapeHtml(label)}</span><small>${button.value.toFixed(2)}</small></div>`;
}

function stickControl(pad, buttonIndex, label, xAxis, yAxis) {
  const x = Math.max(-1, Math.min(1, pad.axes[xAxis] || 0));
  const y = Math.max(-1, Math.min(1, pad.axes[yAxis] || 0));
  const button = pad.buttons[buttonIndex] || { pressed: false, value: 0 };
  return `<div class="stick-wrap"><div class="stick ${button.pressed ? "pressed" : ""}" title="${escapeHtml(label)} · 按钮 ${buttonIndex}"><span class="stick-knob" style="--stick-x:${x * 16}px;--stick-y:${y * 16}px"></span></div><span>${escapeHtml(label)}</span></div>`;
}

function controllerDiagram(pad, labels) {
  return `<div class="controller-visual" aria-label="${labels.family} 手柄实时按键图">
    <div class="controller-family">${labels.family}</div>
    <div class="shoulder-row">
      ${visualButton(pad, 6, labels.shoulders[2], `${labels.shoulders[2]} 左扳机`, "trigger")}
      ${visualButton(pad, 4, labels.shoulders[0], `${labels.shoulders[0]} 左肩键`, "shoulder")}
      ${visualButton(pad, 5, labels.shoulders[1], `${labels.shoulders[1]} 右肩键`, "shoulder")}
      ${visualButton(pad, 7, labels.shoulders[3], `${labels.shoulders[3]} 右扳机`, "trigger")}
    </div>
    <div class="controller-body">
      <div class="dpad" aria-label="十字方向键">
        <span></span>${visualButton(pad, 12, "↑", "十字键上", "dpad-key")}<span></span>
        ${visualButton(pad, 14, "←", "十字键左", "dpad-key")}<span class="dpad-center">十字键</span>${visualButton(pad, 15, "→", "十字键右", "dpad-key")}
        <span></span>${visualButton(pad, 13, "↓", "十字键下", "dpad-key")}<span></span>
      </div>
      <div class="center-buttons">
        <div>${visualButton(pad, 8, labels.center[0], `${labels.center[0]} 功能键`, "system")}${visualButton(pad, 9, labels.center[1], `${labels.center[1]} 功能键`, "system")}</div>
        ${visualButton(pad, 16, labels.center[2], `${labels.center[2]} 主键`, "home-key")}
      </div>
      <div class="face-buttons" aria-label="动作键">
        <span></span>${visualButton(pad, 3, labels.face[3], labels.faceNames[3], "face face-top")}<span></span>
        ${visualButton(pad, 2, labels.face[2], labels.faceNames[2], "face face-left")}<span class="face-center">动作键</span>${visualButton(pad, 1, labels.face[1], labels.faceNames[1], "face face-right")}
        <span></span>${visualButton(pad, 0, labels.face[0], labels.faceNames[0], "face face-bottom")}<span></span>
      </div>
    </div>
    <div class="sticks-row">
      ${stickControl(pad, 10, labels.sticks[0], 0, 1)}
      ${stickControl(pad, 11, labels.sticks[1], 2, 3)}
    </div>
  </div>`;
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value;
  return node.innerHTML;
}

function gamepadSnapshot() {
  return Array.from(navigator.getGamepads?.() || []).filter(Boolean).map((pad) => ({
    id: pad.id,
    index: pad.index,
    mapping: pad.mapping,
    timestamp: pad.timestamp,
    axes: Array.from(pad.axes, (value) => Number(value.toFixed(4))),
    buttons: Array.from(pad.buttons, (button) => ({
      pressed: button.pressed,
      touched: button.touched,
      value: Number(button.value.toFixed(4)),
    })),
  }));
}

function runSender() {
  const start = $("#start");
  const fullscreen = $("#fullscreen");
  const rotate = $("#rotate");
  const output = $("#gamepads");
  let socket;
  let running = false;
  let lastPayload = "";
  let lastSent = 0;
  const keyboard = new Map();
  let nativeFullscreen = false;
  let landscapeDirection = null;

  function updateViewportHeight() {
    document.documentElement.style.setProperty(
      "--app-height", `${window.innerHeight}px`);
  }

  async function lockLandscape() {
    if (landscapeDirection && screen.orientation?.lock) {
      try {
        await screen.orientation.lock(landscapeDirection);
        return true;
      } catch (_error) {
        // Some browsers only allow orientation locking in installed apps.
      }
    }
    return false;
  }

  function unlockOrientation() {
    if (screen.orientation?.unlock) screen.orientation.unlock();
  }

  function setFocusMode(enabled) {
    document.body.classList.toggle("sender-focus", enabled);
    if (!enabled) {
      document.body.classList.remove(
        "manual-landscape", "manual-landscape-reverse", "manual-flip");
    }
    fullscreen.setAttribute("aria-label", enabled ? "退出全屏" : "进入全屏");
    fullscreen.title = enabled ? "退出全屏" : "进入全屏";
    fullscreen.querySelector("span").textContent = enabled ? "×" : "⛶";
  }

  function applyManualLandscape(enabled) {
    document.body.classList.toggle("manual-landscape", enabled);
    document.body.classList.toggle(
      "manual-landscape-reverse",
      enabled && landscapeDirection === "landscape-secondary");
  }

  fullscreen.addEventListener("click", async () => {
    const enabled = !document.body.classList.contains("sender-focus");
    setFocusMode(enabled);
    if (enabled) {
      landscapeDirection = null;
      unlockOrientation();
      document.body.classList.remove(
        "manual-landscape", "manual-landscape-reverse", "manual-flip");
      // Mobile browsers may preserve the orientation at the moment native
      // fullscreen starts. Use CSS focus mode on touch devices so automatic
      // phone rotation remains in control.
      const isTouchDevice = matchMedia("(pointer: coarse)").matches;
      if (!isTouchDevice && document.documentElement.requestFullscreen) {
        try {
          await document.documentElement.requestFullscreen();
          nativeFullscreen = true;
        } catch (_error) {
          nativeFullscreen = false;
        }
      }
      updateViewportHeight();
    } else {
      landscapeDirection = null;
      unlockOrientation();
      if (document.fullscreenElement) {
        try {
          await document.exitFullscreen();
        } catch (_error) {
          // The CSS focus layout can still exit without native fullscreen.
        }
      }
    }
  });

  rotate.addEventListener("click", async () => {
    if (landscapeDirection === null) {
      const currentDirection = screen.orientation?.type;
      landscapeDirection = currentDirection === "landscape-primary"
        ? "landscape-secondary"
        : "landscape-primary";
    } else {
      landscapeDirection = landscapeDirection === "landscape-primary"
        ? "landscape-secondary"
        : "landscape-primary";
    }
    const orientationLocked = await lockLandscape();
    if (orientationLocked) {
      applyManualLandscape(false);
      document.body.classList.remove("manual-flip");
    } else {
      const portrait = matchMedia("(orientation: portrait)").matches;
      applyManualLandscape(portrait);
      document.body.classList.toggle("manual-flip", !portrait);
    }
    updateViewportHeight();
  });

  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && nativeFullscreen) {
      nativeFullscreen = false;
      unlockOrientation();
      setFocusMode(false);
    }
  });

  window.addEventListener("orientationchange", () => {
    setTimeout(() => {
      if (matchMedia("(orientation: landscape)").matches) {
        applyManualLandscape(false);
      }
      updateViewportHeight();
    }, 150);
  });
  window.addEventListener("resize", updateViewportHeight);
  updateViewportHeight();

  $("#secure-value").textContent = window.isSecureContext ? "是" : "否";
  $("#api-value").textContent = navigator.getGamepads ? "可用" : "不可用";
  $("#browser-value").textContent = navigator.userAgent;

  function updateDeviceStatus(gamepads) {
    const deviceStatus = $("#device-status");
    if (gamepads.length) {
      deviceStatus.className = "notice device-status success";
      deviceStatus.textContent = `已识别 ${gamepads.length} 个 Gamepad 设备`;
    } else if (keyboard.size) {
      deviceStatus.className = "notice device-status warning";
      deviceStatus.textContent = "检测到键盘模式输入，正在使用兼容回传";
    } else {
      deviceStatus.className = "notice device-status warning";
      deviceStatus.textContent = "网络已连接，但浏览器未发现手柄。请按手柄任意键，或切换到 Android/XInput 模式。";
    }
    $("#pad-count").textContent = String(gamepads.length);
    $("#keyboard-count").textContent = String(keyboard.size);
  }

  window.addEventListener("gamepadconnected", (event) => {
    updateDeviceStatus(gamepadSnapshot());
    $("#last-event").textContent = `已连接：${event.gamepad.id}`;
  });
  window.addEventListener("gamepaddisconnected", (event) => {
    updateDeviceStatus(gamepadSnapshot());
    $("#last-event").textContent = `已断开：${event.gamepad.id}`;
  });
  window.addEventListener("keydown", (event) => {
    if (event.repeat) return;
    keyboard.set(event.code, { code: event.code, key: event.key });
    updateDeviceStatus(gamepadSnapshot());
    event.preventDefault();
  });
  window.addEventListener("keyup", (event) => {
    keyboard.delete(event.code);
    updateDeviceStatus(gamepadSnapshot());
    event.preventDefault();
  });

  if (!window.isSecureContext || !navigator.getGamepads) {
    start.disabled = true;
    $("#sender-help").innerHTML = '<span class="error-text">当前浏览器不能读取手柄。请确认已信任本站 CA，并使用最新版 Chrome 或 Safari。</span>';
    setConnection("error", "环境不受支持");
    return;
  }

  function connect() {
    socket = new WebSocket(websocketUrl("sender"));
    socket.addEventListener("open", () => setConnection("online", "已连接电脑"));
    socket.addEventListener("close", () => {
      setConnection("error", "正在重连");
      if (running) setTimeout(connect, 1000);
    });
  }

  function frame(now) {
    if (!running) return;
    const gamepads = gamepadSnapshot();
    const keyboardKeys = Array.from(keyboard.values());
    renderInputs(gamepads, keyboardKeys, output);
    updateDeviceStatus(gamepads);
    const snapshot = JSON.stringify([gamepads, keyboardKeys]);
    if (socket?.readyState === WebSocket.OPEN &&
        (snapshot !== lastPayload || now - lastSent > 500)) {
      socket.send(JSON.stringify({
        type: "gamepads",
        sentAt: Date.now(),
        gamepads,
        keyboard: keyboardKeys,
        client: {
          userAgent: navigator.userAgent,
          platform: navigator.platform,
          secureContext: window.isSecureContext,
        },
      }));
      lastPayload = snapshot;
      lastSent = now;
    }
    requestAnimationFrame(frame);
  }

  start.addEventListener("click", () => {
    running = true;
    document.body.classList.add("transmitting");
    start.disabled = true;
    start.textContent = "正在传输";
    $("#device-status").hidden = false;
    connect();
    requestAnimationFrame(frame);
  });
}

function runMonitor() {
  const output = $("#gamepads");
  const latency = $("#latency");
  const rate = $("#rate");
  const senders = $("#senders");
  let frames = 0;
  let rateStartedAt = performance.now();

  fetch("/api/config").then((response) => response.json()).then((config) => {
    $("#phone-url").textContent = config.phoneUrl;
    $("#phone-url").href = config.phoneUrl;
  });

  function connect() {
    const socket = new WebSocket(websocketUrl("receiver"));
    socket.addEventListener("open", () => setConnection("online", "监视端已连接"));
    socket.addEventListener("close", () => {
      setConnection("error", "正在重连");
      setTimeout(connect, 1000);
    });
    socket.addEventListener("message", (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "peers") {
        senders.textContent = data.senders;
        return;
      }
      if (data.type !== "gamepads") return;
      renderInputs(data.gamepads || [], data.keyboard || [], output);
      if (data.client) {
        $("#client-info").textContent = `${data.client.platform || "未知平台"} · ${data.client.userAgent || "未知浏览器"}`;
      }
      latency.textContent = Math.max(0, Date.now() - data.sentAt);
      frames += 1;
      const now = performance.now();
      if (now - rateStartedAt >= 1000) {
        rate.textContent = Math.round(frames * 1000 / (now - rateStartedAt));
        frames = 0;
        rateStartedAt = now;
      }
    });
  }
  connect();
}

document.body.dataset.page === "sender" ? runSender() : runMonitor();
