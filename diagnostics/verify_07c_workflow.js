#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const workflowPath = path.resolve(
  __dirname,
  "..",
  "PROJETO_SM3_07C_VARIANT_SELECTION_EDIT_SESSION_v1.json",
);
const workflow = JSON.parse(fs.readFileSync(workflowPath, "utf8"));

function fail(message) {
  throw new Error(message);
}

const names = new Set(workflow.nodes.map((node) => node.name));
if (names.size !== workflow.nodes.length) fail("DUPLICATE_NODE_NAMES");
const ids = new Set(workflow.nodes.map((node) => node.id));
if (ids.size !== workflow.nodes.length) fail("DUPLICATE_NODE_IDS");

for (const [source, connection] of Object.entries(workflow.connections)) {
  if (!names.has(source)) fail(`MISSING_CONNECTION_SOURCE:${source}`);
  for (const output of connection.main || []) {
    for (const edge of output) {
      if (!names.has(edge.node)) fail(`MISSING_CONNECTION_TARGET:${edge.node}`);
    }
  }
}

for (const node of workflow.nodes.filter((item) => item.type === "n8n-nodes-base.code")) {
  try {
    new Function(node.parameters.jsCode);
  } catch (error) {
    fail(`INVALID_CODE_NODE:${node.name}:${error.message}`);
  }
}

const queueNode = workflow.nodes.find(
  (node) => node.name === "BUILD — SELECTION COMMIT QUEUE",
);
if (!queueNode) fail("QUEUE_NODE_NOT_FOUND");
const runQueue = new Function("$input", queueNode.parameters.jsCode);

const base = {
  ID_PROJETO: "TATTOO_0002",
  ID_CONTEÚDO: "CARROSSEL_0004",
  VARIANT_SET_ID: "VS_TEST",
  VARIANT_COUNT: 3,
  VARIANT_REVIEW_STATUS: "PREVIEW_READY",
  SELECTED_VARIANT_ID: "",
  REVISION_MODE: "UNDECIDED",
  EDIT_SESSION_ID: "",
  EDIT_SESSION_STATUS: "NOT_STARTED",
  RENDER_STATUS: "VARIANT_PREVIEWS_READY",
  PIPELINE_STATE: "VARIANT_REVIEW_READY",
  STATE_VERSION: "SM3_STATE_V4",
  PRODUCTION_CONTRACT_VERSION: "SM3_PRODUCTION_EDIT_V1",
};

function route(rows) {
  return runQueue({all: () => rows.map((json) => ({json}))}).map((item) => item.json);
}

let result = route([base]);
if (result.length !== 1 || result[0].route_key !== "NO_WORK") {
  fail("NO_SELECTION_MUST_NOT_START_SESSION");
}

result = route([{...base, VARIANT_REVIEW_STATUS: "SELECTED", SELECTED_VARIANT_ID: "V02"}]);
if (result.length !== 1 || result[0].route_key !== "START" || result[0].variant_id !== "V02") {
  fail("EXPLICIT_SELECTION_NOT_ROUTED_TO_START");
}

result = route([{...base, SELECTED_VARIANT_ID: "V02"}]);
if (result.length !== 1 || result[0].route_key !== "BLOCKED") {
  fail("PARTIAL_SELECTION_MUST_FAIL_CLOSED");
}

result = route([{...base, VARIANT_REVIEW_STATUS: "SELECTED", SELECTED_VARIANT_ID: "V04"}]);
if (result.length !== 1 || result[0].route_key !== "BLOCKED") {
  fail("OUT_OF_RANGE_SELECTION_MUST_FAIL_CLOSED");
}

const duplicateSelection = {
  ...base,
  VARIANT_REVIEW_STATUS: "SELECTED",
  SELECTED_VARIANT_ID: "V01",
};
result = route([duplicateSelection, {...duplicateSelection}]);
if (result.length !== 1 || result[0].route_key !== "BLOCKED") {
  fail("DUPLICATE_CONTENT_ID_MUST_FAIL_CLOSED");
}

result = route([{
  ...base,
  VARIANT_REVIEW_STATUS: "OPEN_EDITOR",
  SELECTED_VARIANT_ID: "V01",
  REVISION_MODE: "VARIANT_SELECTION",
  EDIT_SESSION_ID: "ES_TEST",
  EDIT_SESSION_STATUS: "OPEN",
  PIPELINE_STATE: "EDIT_SESSION_READY",
  STATE_VERSION: "SM3_STATE_V5",
}]);
if (result.length !== 1 || result[0].route_key !== "NO_WORK" || result[0].existing_sessions !== 1) {
  fail("COMMITTED_SESSION_MUST_BE_IDEMPOTENT_NO_WORK");
}

console.log(`SM3_07C_WORKFLOW_CONTRACT_PASS nodes=${workflow.nodes.length}`);
console.log("explicit_selection=START");
console.log("partial_selection=FAIL_CLOSED");
console.log("duplicate_content_id=FAIL_CLOSED");
console.log("committed_session=NO_WORK");
