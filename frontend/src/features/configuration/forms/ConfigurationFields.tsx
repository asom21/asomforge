// 渲染各类配置的专属字段和输入提示。
import type { ReactNode } from 'react';
import type { Kind } from '../../../api/client';
import { platformNames } from '../catalog';
import type { Values } from './values';

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function ConfigurationFields({
  kind,
  values: v,
  set,
  secretFields,
}: {
  kind: Kind;
  values: Values;
  set: (key: keyof Values, value: string) => void;
  secretFields: string[];
}) {
  const input = (key: keyof Values, placeholder = '', required = false, type = 'text') => (
    <input
      value={v[key]}
      onChange={(e) => set(key, e.target.value)}
      placeholder={placeholder}
      required={required}
      type={type}
      autoComplete="off"
    />
  );
  const area = (key: keyof Values, rows = 4, placeholder = '') => (
    <textarea
      className="code-input"
      value={v[key]}
      onChange={(e) => set(key, e.target.value)}
      rows={rows}
      placeholder={placeholder}
      spellCheck={false}
    />
  );
  const select = (key: keyof Values, options: Record<string, string>) => (
    <select value={v[key]} onChange={(e) => set(key, e.target.value)}>
      {Object.entries(options).map(([value, title]) => (
        <option key={value} value={value}>
          {title}
        </option>
      ))}
    </select>
  );
  const launch = (
    <>
      <Field
        label="启动命令"
        hint={
          kind === 'platforms' ? '留空使用平台默认命令。' : '填写可执行程序名或路径，不包含参数。'
        }
      >
        {input('command', kind === 'platforms' ? '使用默认命令' : '例如 npx', kind === 'mcp')}
      </Field>
      <Field label="参数" hint="JSON 字符串数组，每个参数单独一项。">
        {area('args', 3, '["--flag"]')}
      </Field>
      <Field label="工作目录" hint="留空使用本地数据目录；相对路径也以该目录为起点。">
        {input('cwd', '可选：工作目录路径')}
      </Field>
      <Field label="环境变量" hint="JSON 对象。值存入私密文件；已有值留空表示保留。">
        {area('env', 4, '{"API_KEY": "…"}')}
      </Field>
    </>
  );
  return (
    <>
      {kind === 'skills' && (
        <Field
          label="SKILL.md"
          hint="YAML frontmatter 需要 name 和 description。标准包名与显示名称分别管理。"
        >
          {area('content', 16)}
        </Field>
      )}
      {kind === 'prompts' && (
        <>
          <Field label="指令正文" hint="使用 {{变量名}} 预留任务输入。">
            {area('content', 13, '例如：请分析 {{需求}}，输出实施建议。')}
          </Field>
          <Field label="变量声明" hint="逗号分隔；留空时自动提取正文中的变量。">
            {input('variables', '例如 goal, context')}
          </Field>
        </>
      )}
      {kind === 'mcp' && (
        <>
          <Field label="连接方式">
            {select('transport', {
              stdio: 'stdio · 本地进程',
              http: 'Streamable HTTP',
              sse: 'SSE · 旧版传输',
            })}
          </Field>
          {v.transport === 'stdio' ? (
            launch
          ) : (
            <>
              <Field label="服务地址">{input('url', 'https://example.com/mcp', true, 'url')}</Field>
              <Field label="请求头" hint="JSON 对象。值保存在私密文件，普通配置不回显。">
                {area('headers', 5)}
              </Field>
            </>
          )}
        </>
      )}
      {kind === 'models' && (
        <>
          <Field label="接口协议">
            {select('protocol', { openai: 'OpenAI 兼容', anthropic: 'Anthropic' })}
          </Field>
          <Field
            label="API 基础地址"
            hint="填写协议根地址，例如 https://api.example.com/v1。检查会在其后追加 /models。"
          >
            {input('baseUrl', 'https://api.example.com/v1', true, 'url')}
          </Field>
          <Field
            label="API Key"
            hint={
              secretFields.includes('api_key')
                ? '已保存凭据。留空保留，填写新值替换。'
                : '仅保存在本机私密文件，不写入普通配置。'
            }
          >
            {input(
              'apiKey',
              secretFields.includes('api_key') ? '已保存 · 留空保留' : '填写 API Key',
              false,
              'password',
            )}
          </Field>
          <Field label="模型标识" hint="可选；检查时核对模型是否出现在列表中。">
            {input('model', '例如 deepseek-chat')}
          </Field>
        </>
      )}
      {kind === 'platforms' && (
        <>
          <Field label="平台类型">{select('platform', platformNames)}</Field>
          {launch}
        </>
      )}
    </>
  );
}
