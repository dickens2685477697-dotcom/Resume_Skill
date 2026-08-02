#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const [sourcePath, outputDirectory] = process.argv.slice(2);

if (!sourcePath || !outputDirectory) {
  console.error('Usage: node export_flowchart_svgs.mjs <visualization.html> <output-directory>');
  process.exit(1);
}

const source = fs.readFileSync(sourcePath, 'utf8');
const match = source.match(/const boundaryFlows = (\{[\s\S]*?\n  \});\n\n  Object\.assign\(defaults, boundaryFlows\);/);

if (!match) {
  throw new Error('Could not find boundaryFlows in the visualization source.');
}

const flows = vm.runInNewContext(`(${match[1]})`);
const grid = [
  [140, 110], [460, 110], [780, 110], [1100, 110],
  [1100, 510], [780, 510], [460, 510], [140, 510],
  [280, 310], [600, 310], [920, 310], [1240, 310],
  [1240, 710], [920, 710], [600, 710], [280, 710],
];

for (const flow of Object.values(flows)) {
  flow.nodes.forEach((node, index) => {
    if (grid[index]) [node.x, node.y] = grid[index];
  });
}

const fileNames = {
  full: 'resume-tailor-full-workflow.svg',
  resume: 'resume-input-workflow.svg',
  jd: 'jd-input-workflow.svg',
};

function escapeXml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function dimensions(node) {
  if (node.type === 'decision') return { w: 240, h: 124 };
  if (node.type === 'terminal') return { w: 240, h: 86 };
  if (node.type === 'store') return { w: 250, h: 110 };
  return { w: 250, h: 104 };
}

function nodePalette(type) {
  if (type === 'decision') return { fill: '#FFF2CC', stroke: '#D6A64F' };
  if (type === 'store') return { fill: '#E8F1FF', stroke: '#6F93C5' };
  if (type === 'input') return { fill: '#EAF3FF', stroke: '#6F93C5' };
  if (type === 'warning') return { fill: '#FFF0F0', stroke: '#E06B6B' };
  return { fill: '#E9F7EF', stroke: '#67A77F' };
}

function wrapText(value, limit, maxLines = 2) {
  const lines = [];
  for (const explicitLine of String(value ?? '').split('\n')) {
    let remaining = explicitLine;
    while (remaining.length > limit && lines.length < maxLines - 1) {
      let cut = limit;
      const punctuation = Math.max(
        remaining.lastIndexOf('，', limit),
        remaining.lastIndexOf('、', limit),
        remaining.lastIndexOf('/', limit),
        remaining.lastIndexOf(' ', limit),
      );
      if (punctuation > 4) cut = punctuation + 1;
      lines.push(remaining.slice(0, cut));
      remaining = remaining.slice(cut);
    }
    if (remaining && lines.length < maxLines) lines.push(remaining);
    if (lines.length >= maxLines) break;
  }
  if (lines.length === maxLines && lines.at(-1).length > limit + 3) {
    lines[lines.length - 1] = `${lines.at(-1).slice(0, limit + 2)}…`;
  }
  return lines;
}

function shapeSvg(node) {
  const { w, h } = dimensions(node);
  const palette = nodePalette(node.type);
  const shapeAttributes = `fill="${palette.fill}" stroke="${palette.stroke}" stroke-width="1.8"`;
  if (node.type === 'decision') {
    return `<polygon class="node-shape" ${shapeAttributes} points="0,${-h / 2} ${w / 2},0 0,${h / 2} ${-w / 2},0"/>`;
  }
  if (node.type === 'input') {
    const skew = 24;
    return `<polygon class="node-shape" ${shapeAttributes} points="${-w / 2 + skew},${-h / 2} ${w / 2},${-h / 2} ${w / 2 - skew},${h / 2} ${-w / 2},${h / 2}"/>`;
  }
  if (node.type === 'store') {
    return [
      `<path class="node-shape" ${shapeAttributes} d="M ${-w / 2} ${-h / 2 + 14} C ${-w / 2} ${-h / 2 - 4}, ${w / 2} ${-h / 2 - 4}, ${w / 2} ${-h / 2 + 14} L ${w / 2} ${h / 2 - 14} C ${w / 2} ${h / 2 + 4}, ${-w / 2} ${h / 2 + 4}, ${-w / 2} ${h / 2 - 14} Z"/>`,
      `<path class="store-rim" fill="none" stroke="${palette.stroke}" stroke-width="1.4" d="M ${-w / 2} ${-h / 2 + 14} C ${-w / 2} ${-h / 2 + 32}, ${w / 2} ${-h / 2 + 32}, ${w / 2} ${-h / 2 + 14}"/>`,
    ].join('');
  }
  const radius = node.type === 'terminal' ? h / 2 : 10;
  return `<rect class="node-shape" ${shapeAttributes} x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="${radius}"/>`;
}

function nodeTextSvg(node) {
  const titleLines = wrapText(node.label, node.type === 'decision' ? 11 : 13, 2);
  const stageLines = node.stage ? wrapText(node.stage, 18, 2) : [];
  const titleHeight = titleLines.length * 23;
  const stageHeight = stageLines.length * 17;
  const gap = stageLines.length ? 9 : 0;
  const totalHeight = titleHeight + gap + stageHeight;
  const titleStart = -totalHeight / 2 + 17;
  const title = titleLines.map((line, index) =>
    `<tspan x="0" y="${titleStart + index * 23}">${escapeXml(line)}</tspan>`
  ).join('');
  const stageStart = titleStart + titleLines.length * 23 + gap - 2;
  const stage = stageLines.map((line, index) =>
    `<tspan x="0" y="${stageStart + index * 17}">${escapeXml(line)}</tspan>`
  ).join('');
  const fontFamily = 'Inter, PingFang SC, Microsoft YaHei, Arial, sans-serif';
  return `<text class="node-title" fill="#132238" font-family="${fontFamily}" font-size="20" font-weight="500" text-anchor="middle">${title}</text>${stage ? `<text class="node-stage" fill="#475569" font-family="${fontFamily}" font-size="13" font-weight="400" text-anchor="middle">${stage}</text>` : ''}`;
}

function anchor(node, target) {
  const { w, h } = dimensions(node);
  const dx = target.x - node.x;
  const dy = target.y - node.y;
  if (Math.abs(dx) > Math.abs(dy)) {
    return { x: node.x + Math.sign(dx || 1) * w / 2, y: node.y };
  }
  return { x: node.x, y: node.y + Math.sign(dy || 1) * h / 2 };
}

function edgeGeometry(edge, nodeMap) {
  const from = nodeMap.get(edge.from);
  const to = nodeMap.get(edge.to);
  if (!from || !to) return null;
  const start = anchor(from, to);
  const end = anchor(to, from);
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (Math.abs(dx) < 28 || Math.abs(dy) < 28) {
    return {
      d: `M ${start.x} ${start.y} L ${end.x} ${end.y}`,
      labelX: (start.x + end.x) / 2,
      labelY: (start.y + end.y) / 2 - 12,
    };
  }
  if (Math.abs(dy) >= Math.abs(dx) * 0.72) {
    const midY = (start.y + end.y) / 2;
    return {
      d: `M ${start.x} ${start.y} L ${start.x} ${midY} L ${end.x} ${midY} L ${end.x} ${end.y}`,
      labelX: (start.x + end.x) / 2,
      labelY: midY - 12,
    };
  }
  const midX = (start.x + end.x) / 2;
  return {
    d: `M ${start.x} ${start.y} L ${midX} ${start.y} L ${midX} ${end.y} L ${end.x} ${end.y}`,
    labelX: midX,
    labelY: (start.y + end.y) / 2 - 12,
  };
}

function renderFlow(flow, key) {
  const nodeMap = new Map(flow.nodes.map(node => [node.id, node]));
  const edges = flow.edges.map(edge => {
    const geometry = edgeGeometry(edge, nodeMap);
    if (!geometry) return '';
    const warning = edge.tone === 'warning';
    return [
      `<g id="${escapeXml(edge.id)}" class="edge-group${warning ? ' warning' : ''}">`,
      `<path class="edge" fill="none" stroke="${warning ? '#DC2626' : '#64748B'}" stroke-width="2" d="${geometry.d}" marker-end="url(#${warning ? 'arrow-warning' : 'arrow'})"/>`,
      edge.label ? `<text class="edge-label" x="${geometry.labelX}" y="${geometry.labelY}" fill="#334155" stroke="#FFFFFF" stroke-width="7" paint-order="stroke" stroke-linejoin="round" font-family="Inter, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="14" font-weight="500" text-anchor="middle">${escapeXml(edge.label)}</text>` : '',
      '</g>',
    ].join('');
  }).join('\n');

  const nodes = flow.nodes.map(node => [
    `<g id="${escapeXml(node.id)}" class="node ${escapeXml(node.type)}" transform="translate(${node.x} ${node.y})" data-node-type="${escapeXml(node.type)}">`,
    `<title>${escapeXml(node.label)}${node.stage ? ` — ${escapeXml(node.stage)}` : ''}</title>`,
    shapeSvg(node),
    nodeTextSvg(node),
    '</g>',
  ].join('')).join('\n');

  const laneLabels = [
    ['主流程 · 前半', 28],
    ['边界条件 · 前半', 228],
    ['主流程 · 后半', 428],
    ['边界条件 · 后半', 628],
  ].map(([label, y]) => `<text class="lane-label" x="24" y="${y}" fill="#64748B" font-family="Inter, PingFang SC, Microsoft YaHei, Arial, sans-serif" font-size="14" font-weight="500">${label}</text>`).join('\n');

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">
  <title id="title">${escapeXml(flow.name)} — Resume Tailor 四行流程图</title>
  <desc id="desc">主流程分为前后两行，每段主流程下方展示对应的异常、停止和证据边界条件。</desc>
  <metadata>Editable vector export generated from Resume Tailor workflow definitions. Flow key: ${escapeXml(key)}</metadata>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#64748b"/></marker>
    <marker id="arrow-warning" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#dc2626"/></marker>
  </defs>
  <rect id="background" class="background" width="1600" height="900" fill="#FFFFFF"/>
  <g id="lane-guides">
    <line class="lane-rule" x1="20" y1="42" x2="1580" y2="42" stroke="#E2E8F0" stroke-width="1"/>
    <line class="lane-rule" x1="20" y1="242" x2="1580" y2="242" stroke="#E2E8F0" stroke-width="1"/>
    <line class="lane-rule" x1="20" y1="442" x2="1580" y2="442" stroke="#E2E8F0" stroke-width="1"/>
    <line class="lane-rule" x1="20" y1="642" x2="1580" y2="642" stroke="#E2E8F0" stroke-width="1"/>
    ${laneLabels}
  </g>
  <g id="edges">${edges}</g>
  <g id="nodes">${nodes}</g>
</svg>`;
}

fs.mkdirSync(outputDirectory, { recursive: true });

for (const [key, flow] of Object.entries(flows)) {
  const destination = path.join(outputDirectory, fileNames[key]);
  fs.writeFileSync(destination, `${renderFlow(flow, key)}\n`, 'utf8');
  console.log(destination);
}
