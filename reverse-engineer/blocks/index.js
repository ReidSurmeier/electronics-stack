// blocks/index.js — registry of all available blocks. Spec files refer to
// blocks by their `id` (matches filename without .js).

const fs = require("fs");
const path = require("path");

const registry = {};
const files = fs.readdirSync(__dirname).filter((f) => f.endsWith(".js") && f !== "index.js");
for (const f of files) {
  const blk = require(path.join(__dirname, f));
  if (!blk || !blk.id) {
    throw new Error(`Block ${f} missing 'id' export`);
  }
  registry[blk.id] = blk;
}

module.exports = registry;
