// 微信开发者工具 MCP 服务
const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const { CallToolRequestSchema, ListToolsRequestSchema } = require('@modelcontextprotocol/sdk/types.js');
const automator = require('miniprogram-automator');

const PROJECT_PATH = process.argv[2] || process.cwd();
let miniProgram = null;
let consoleLogs = [];
let pageErrors = [];

const server = new Server(
  { name: 'wechat-devtools-mcp', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

async function ensureConnected() {
  if (!miniProgram) {
    console.error('[MCP] Connecting to WeChat DevTools...');
    try {
      // 尝试连接已运行的 DevTools 实例
      miniProgram = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:' + (process.argv[3] || '64265') });
      miniProgram.on('console', (log) => {
        consoleLogs.push({
          level: log.level,
          message: log.text,
          timestamp: new Date().toISOString()
        });
        if (consoleLogs.length > 200) consoleLogs.shift();
      });
      miniProgram.on('error', (err) => {
        pageErrors.push({
          message: err.message || String(err),
          timestamp: new Date().toISOString()
        });
      });
      console.error('[MCP] Connected successfully.');
    } catch (err) {
      console.error('[MCP] Connection failed:', err.message);
      throw err;
    }
  }
  return miniProgram;
}

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'get_errors',
      description: '获取小程序控制台所有错误和警告',
      inputSchema: { type: 'object', properties: {} }
    },
    {
      name: 'get_console_logs',
      description: '获取控制台全部日志（最近200条）',
      inputSchema: {
        type: 'object',
        properties: {
          level: { type: 'string', description: '过滤级别: error/warn/info/log', default: 'all' }
        }
      }
    },
    {
      name: 'reload',
      description: '强制刷新模拟器，触发重新编译',
      inputSchema: { type: 'object', properties: {} }
    },
    {
      name: 'get_page_data',
      description: '获取当前页面的 data 数据',
      inputSchema: { type: 'object', properties: {} }
    },
    {
      name: 'navigate',
      description: '导航到指定页面',
      inputSchema: {
        type: 'object',
        properties: {
          url: { type: 'string', description: '页面路径，如 /pages/index/index' }
        },
        required: ['url']
      }
    },
    {
      name: 'screenshot',
      description: '截图当前模拟器页面',
      inputSchema: { type: 'object', properties: {} }
    }
  ]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const mp = await ensureConnected();

  try {
    switch (request.params.name) {
      case 'get_errors': {
        const errors = consoleLogs.filter(l => l.level === 'error' || l.level === 'warn');
        const allErrors = [...pageErrors, ...errors];
        return { content: [{ type: 'text', text: allErrors.length ? JSON.stringify(allErrors, null, 2) : '无错误' }] };
      }

      case 'get_console_logs': {
        const level = request.params.arguments?.level || 'all';
        let logs = consoleLogs;
        if (level !== 'all') {
          logs = logs.filter(l => l.level === level);
        }
        return { content: [{ type: 'text', text: JSON.stringify(logs.slice(-50), null, 2) }] };
      }

      case 'reload': {
        consoleLogs = [];
        pageErrors = [];
        return { content: [{ type: 'text', text: '请手动刷新模拟器（MCP reload 暂不支持此版本 DevTools）' }] };
      }

      case 'get_page_data': {
        const page = await mp.currentPage();
        const data = await page.data();
        return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }] };
      }

      case 'navigate': {
        const url = request.params.arguments.url;
        await mp.navigateTo(url);
        await new Promise(r => setTimeout(r, 2000));
        const page = await mp.currentPage();
        return { content: [{ type: 'text', text: `已导航到 ${url}，当前页面: ${page.path}` }] };
      }

      case 'screenshot': {
        const page = await mp.currentPage();
        const img = await page.screenshot();
        return { content: [{ type: 'text', text: `截图完成 (${img.length} bytes)` }] };
      }

      default:
        throw new Error(`Unknown tool: ${request.params.name}`);
    }
  } catch (err) {
    return { content: [{ type: 'text', text: `错误: ${err.message}` }], isError: true };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('[MCP] Server running on Stdio');
}
main().catch(err => { console.error('[MCP] Fatal:', err); process.exit(1); });
