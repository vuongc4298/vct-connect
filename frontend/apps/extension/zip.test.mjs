import assert from "node:assert/strict";
import test from "node:test";
import { inflateRawSync } from "node:zlib";
import { createZip } from "./zip.mjs";

test("ZIP is deterministic and stores readable central/local entries", () => {
  const files = [{ name: "manifest.json", data: Buffer.from('{"version":"0.7.0"}') }, { name: "icon.png", data: Buffer.from([0, 1, 2, 255]) }];
  const archive = createZip(files);
  assert.deepEqual(archive, createZip(files));
  const end = archive.subarray(-22);
  assert.equal(end.readUInt32LE(0), 0x06054b50); assert.equal(end.readUInt16LE(10), 2);
  let central = end.readUInt32LE(16);
  for (const file of files) {
    assert.equal(archive.readUInt32LE(central), 0x02014b50);
    const offset = archive.readUInt32LE(central + 42), nameLength = archive.readUInt16LE(offset + 26);
    assert.equal(archive.readUInt32LE(offset), 0x04034b50);
    assert.equal(archive.subarray(offset + 30, offset + 30 + nameLength).toString(), file.name);
    assert.deepEqual(inflateRawSync(archive.subarray(offset + 30 + nameLength, offset + 30 + nameLength + archive.readUInt32LE(offset + 18))), file.data);
    central += 46 + archive.readUInt16LE(central + 28);
  }
  assert.throws(() => createZip([{ name: "../.env", data: Buffer.alloc(0) }]), /Unsafe/);
});
