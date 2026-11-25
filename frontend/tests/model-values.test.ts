// 验证模型表单容量解析、旧配置转换、候选合并和默认模型约束。
import assert from 'node:assert/strict';
import { test } from 'node:test';

const values = await import('../src/features/configuration/models/values.ts');

test('容量按十进制 K/M 解析，空白保持未声明，拒绝无效与小数 token', () => {
  assert.equal(values.parseCapacity('128K'), 128000);
  assert.equal(values.parseCapacity('1.5M'), 1500000);
  assert.equal(values.parseCapacity(''), undefined);
  for (const raw of ['0', '-1', 'abc', '1.2', 'Infinity']) {
    assert.throws(() => values.parseCapacity(raw));
  }
});

test('旧单模型配置保留连接和默认模型，API Key 不回显', () => {
  const draft = values.initialConnection({
    name: '旧连接',
    description: '',
    config: {
      protocol: 'openai',
      base_url: 'https://example.com/v1',
      model: 'old-model',
      api_key: '',
    },
  });
  assert.equal(draft.protocol, 'openai-chat-completions');
  assert.equal(draft.models[0].id, 'old-model');
  assert.equal(draft.defaultModelKey, draft.models[0].key);
  assert.equal(draft.apiKey, '');
  assert.equal(values.connectionConfig(draft).default_model_id, 'old-model');
});

test('候选追加不覆盖同 ID 的手工能力和默认选择', () => {
  const draft = values.initialConnection();
  draft.models = [values.newModel({ id: 'known', name: '手工名称', context_window: 500000 })];
  draft.defaultModelKey = draft.models[0].key;
  const next = values.mergeCandidates(draft, [{ id: 'known', name: '远端名称' }, { id: 'new' }]);
  assert.equal(next.models.length, 2);
  assert.equal(next.models[0].name, '手工名称');
  assert.equal(next.models[0].contextWindow, '500K');
  assert.equal(next.defaultModelKey, draft.defaultModelKey);
});

test('保存拒绝重复 ID 和无效默认模型，不将编辑用键写入 API 配置', () => {
  const draft = values.initialConnection();
  draft.baseUrl = 'https://example.com/v1';
  draft.models[0].id = 'm';
  draft.models.push(values.newModel({ id: ' m ' }));
  assert.throws(() => values.connectionConfig(draft), /重复/);
  draft.models.pop();
  draft.defaultModelKey = 'missing';
  assert.throws(() => values.connectionConfig(draft), /默认模型/);
  draft.defaultModelKey = draft.models[0].key;
  const config = values.connectionConfig(draft);
  assert.equal(config.models[0].id, 'm');
  assert.equal('key' in config.models[0], false);
});

test('推理映射保留 off 空值，拒绝仅 off 与 Anthropic 非空映射', () => {
  const draft = values.initialConnection();
  draft.baseUrl = 'https://example.com';
  draft.models[0].id = 'm';
  draft.models[0].reasoning = [
    { level: 'off', value: '' },
    { level: 'high', value: 'high' },
  ];
  assert.deepEqual(values.connectionConfig(draft).models[0].reasoning_efforts, {
    off: null,
    high: 'high',
  });
  draft.models[0].reasoning.pop();
  assert.throws(() => values.connectionConfig(draft), /非 off/);
  draft.models[0].reasoning.push({ level: 'high', value: 'high' });
  draft.protocol = 'anthropic-messages';
  assert.throws(() => values.connectionConfig(draft), /Anthropic/);
});

test('发现草稿忽略尚未填写的目录，保存和测试仍需有效模型', () => {
  const draft = values.initialConnection();
  draft.baseUrl = 'http://localhost:9000/v1';
  assert.deepEqual(values.discoveryConfig(draft).models, []);
  assert.throws(() => values.connectionConfig(draft), /模型 ID/);
});
