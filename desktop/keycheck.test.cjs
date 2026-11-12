// node --test "desktop/*.test.cjs". The sample bodies match tests/test_desktop.py (KeyStateTests).
const test = require('node:test');
const assert = require('node:assert');
const { classifyKeyResponse } = require('./keycheck.cjs');

const INVALID = '{"error":{"code":400,"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT","details":[{"reason":"API_KEY_INVALID"}]}}';
const LEAKED = '{"error":{"code":403,"message":"Your API key was reported as leaked. Please use another API key.","status":"PERMISSION_DENIED"}}';
const DISABLED = '{"error":{"code":403,"message":"Generative Language API has not been used in project 123 before or it is disabled.","status":"PERMISSION_DENIED","details":[{"reason":"SERVICE_DISABLED"}]}}';
const QUOTA = '{"error":{"code":429,"message":"Resource has been exhausted (e.g. check quota).","status":"RESOURCE_EXHAUSTED"}}';
const PLAIN_400 = '{"error":{"code":400,"message":"Invalid JSON payload received.","status":"INVALID_ARGUMENT"}}';
const REGION = '{"error":{"code":403,"message":"User location is not supported for the API use.","status":"PERMISSION_DENIED"}}';

test('a working key is valid', () => assert.strictEqual(classifyKeyResponse(200, '{"models":[]}'), 'valid'));
test('a wrong key is rejected', () => assert.strictEqual(classifyKeyResponse(400, INVALID), 'rejected'));
test('a leaked key is rejected', () => assert.strictEqual(classifyKeyResponse(403, LEAKED), 'rejected'));
test('a key without the Gemini API is disabled', () => assert.strictEqual(classifyKeyResponse(403, DISABLED), 'disabled'));
test('quota, other 400s, region limits and server errors are unknown', () => {
  assert.strictEqual(classifyKeyResponse(429, QUOTA), 'unknown');
  assert.strictEqual(classifyKeyResponse(400, PLAIN_400), 'unknown');
  assert.strictEqual(classifyKeyResponse(403, REGION), 'unknown');
  assert.strictEqual(classifyKeyResponse(503, ''), 'unknown');
  assert.strictEqual(classifyKeyResponse(0, undefined), 'unknown');
});
