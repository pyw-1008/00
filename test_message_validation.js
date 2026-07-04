const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function createElementMock(selector) {
  return {
    selector,
    textContent: "",
    value: "",
    disabled: false,
    innerHTML: "",
    listeners: {},
    children: [],
    className: "",
    type: "",
    name: "",
    rows: 0,
    maxlength: 0,
    placeholder: "",
    addEventListener(eventName, handler) {
      this.listeners[eventName] = handler;
    },
    append(...nodes) {
      this.children.push(...nodes);
    },
  };
}

function createHarness({ messageValue = "", lastMessageAt = 0, now = 10000 } = {}) {
  const elements = new Map();
  const selectors = [
    "#questionTitle",
    "#options",
    "#voteForm",
    "#submitVote",
    "#feedback",
    "#messageForm",
    "#messageInput",
    "#messageCount",
    "#submitMessage",
    "#messageFeedback",
  ];

  selectors.forEach((selector) => {
    elements.set(selector, createElementMock(selector));
  });
  elements.get("#messageInput").value = messageValue;

  const localStorageStore = {};
  if (lastMessageAt) {
    localStorageStore["slice2:lastMessageAt"] = String(lastMessageAt);
  }

  const postCalls = [];
  const context = {
    console,
    Number,
    Date: {
      now: () => now,
    },
    FormData: class {
      get() {
        return null;
      }
    },
    document: {
      querySelector(selector) {
        return elements.get(selector);
      },
      createElement(selector) {
        return createElementMock(selector);
      },
    },
    localStorage: {
      getItem(key) {
        return Object.prototype.hasOwnProperty.call(localStorageStore, key)
          ? localStorageStore[key]
          : null;
      },
      setItem(key, value) {
        localStorageStore[key] = String(value);
      },
    },
    fetch(url, options = {}) {
      if (url === "/api/current-question") {
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              ok: true,
              question: {
                title: "测试题目",
                options: [],
              },
            }),
        });
      }

      if (url === "/api/messages") {
        postCalls.push({ url, options });
        return Promise.resolve({
          json: () =>
            Promise.resolve({
              ok: true,
              message: { id: 1, body: JSON.parse(options.body).body },
            }),
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    },
  };

  vm.createContext(context);
  const scriptPath = path.join(__dirname, "public", "audience.js");
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), context);

  return {
    elements,
    postCalls,
    localStorageStore,
    async submitMessage() {
      await elements.get("#messageForm").listeners.submit({
        preventDefault() {},
      });
    },
  };
}

async function testNormalMessage() {
  const harness = createHarness({ messageValue: "你好", now: 10000 });

  await harness.submitMessage();

  assert.strictEqual(harness.postCalls.length, 1);
  assert.strictEqual(JSON.parse(harness.postCalls[0].options.body).body, "你好");
  assert.strictEqual(harness.elements.get("#messageFeedback").textContent, "已发送");
  assert.strictEqual(harness.localStorageStore["slice2:lastMessageAt"], "10000");
}

async function testEmptyMessageIsBlocked() {
  const harness = createHarness({ messageValue: "   ", now: 10000 });

  await harness.submitMessage();

  assert.strictEqual(harness.postCalls.length, 0);
  assert.strictEqual(harness.elements.get("#messageFeedback").textContent, "请输入留言");
}

async function testTooLongMessageIsBlocked() {
  const harness = createHarness({ messageValue: "好".repeat(51), now: 10000 });

  await harness.submitMessage();

  assert.strictEqual(harness.postCalls.length, 0);
  assert.strictEqual(harness.elements.get("#messageFeedback").textContent, "留言最多 50 字");
}

async function testMessageWithinCooldownIsBlocked() {
  const harness = createHarness({
    messageValue: "第二条",
    lastMessageAt: 9000,
    now: 10000,
  });

  await harness.submitMessage();

  assert.strictEqual(harness.postCalls.length, 0);
  assert.strictEqual(harness.elements.get("#messageFeedback").textContent, "发送太快了，请 2 秒后再试");
}

async function run() {
  await testNormalMessage();
  await testEmptyMessageIsBlocked();
  await testTooLongMessageIsBlocked();
  await testMessageWithinCooldownIsBlocked();
  console.log("4 message validation tests passed");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
