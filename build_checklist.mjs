import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const outDir = 'outputs/lighting-checklist';
await fs.mkdir(outDir, { recursive: true });
const wb = Workbook.create();
const sh = wb.worksheets.add('清单');
sh.showGridLines = false;

sh.mergeCells('A1:H1');
sh.getRange('A1').values = [['开关、插座及灯具数量清单']];
sh.mergeCells('A2:H2');
sh.getRange('A2').values = [['依据手写清单图片整理；“待确认”表示原图字迹或对应关系不够清晰']];

const headers = [['序号','项目','房间/区域1','房间/区域2','房间/区域3','房间/区域4','房间/区域5','合计']];
sh.getRange('A4:H4').values = headers;
const rows = [
  [1,'一开','客厅',null,'2+1',1,1,7],
  [2,'二开','客厅',1,1,2,3,8],
  [3,'三开',null,null,null,2,null,2],
  [4,'五孔插座',3,4,2,8,'2+12',38],
  [5,'空调插座',1,1,null,1,null,3],
  [6,'网线插座',1,1,null,1,null,3],
  [7,'抽油烟机插座',1,null,null,null,1,2],
  [8,'灯具（轨道灯3条、房间门廊灯、大厅灯、卫生间灯等）','按图片备注',null,null,null,null,'待确认'],
  [9,'一开五孔',1,null,null,1,null,2],
  [10,'二开多孔',1,null,null,null,null,1],
  [11,'空白盖板',null,null,null,null,1,1],
  [12,'多孔插座（弱电箱）',null,null,null,null,1,1],
  [13,'筒灯/射灯（图片底部备注）','约30个',null,null,null,null,'待确认'],
  [14,'吸顶灯','2个',null,null,null,null,'待确认'],
  [15,'无线感应灯','2根，约4m',null,null,null,null,'待确认'],
];
sh.getRange('A5:H19').values = rows;
sh.mergeCells('A21:H21');
sh.getRange('A21').values = [['图片底部备注：灯带约30个；胶布2个；无损明装轨道灯2根（约4m）。原图部分文字较潦草，建议现场复核。']];

sh.getRange('A1:H1').format = { fill:'#1F4E78', font:{bold:true,color:'#FFFFFF'}, horizontalAlignment:'center', verticalAlignment:'center' };
sh.getRange('A2:H2').format = { fill:'#D9EAF7', font:{italic:true,color:'#44546A',size:10}, horizontalAlignment:'left', verticalAlignment:'center' };
sh.getRange('A4:H4').format = { fill:'#5B9BD5', font:{bold:true,color:'#FFFFFF'}, horizontalAlignment:'center', verticalAlignment:'center', borders:{preset:'all',style:'thin',color:'#B4C7E7'} };
sh.getRange('A5:H19').format = { verticalAlignment:'center', wrapText:true, borders:{insideHorizontal:{style:'thin',color:'#D9E2F3'}, bottom:{style:'thin',color:'#D9E2F3'}} };
sh.getRange('A5:A19').format.horizontalAlignment = 'center';
sh.getRange('H5:H19').format = { fill:'#E2F0D9', font:{bold:true}, horizontalAlignment:'center', verticalAlignment:'center', borders:{preset:'all',style:'thin',color:'#A9D18E'} };
sh.getRange('A21:H21').format = { fill:'#FFF2CC', font:{color:'#7F6000'}, wrapText:true, verticalAlignment:'center' };
sh.getRange('A1:H1').format.rowHeight = 30;
sh.getRange('A2:H2').format.rowHeight = 24;
sh.getRange('A4:H4').format.rowHeight = 24;
sh.getRange('A5:H19').format.rowHeight = 28;
sh.getRange('A21:H21').format.rowHeight = 38;
for (const [col,w] of [['A',7],['B',24],['C',16],['D',16],['E',16],['F',16],['G',18],['H',12]]) sh.getRange(`${col}1:${col}21`).format.columnWidth = w;
sh.freezePanes.freezeRows(4);
// Keep the source list simple and editable; filters can be added later if needed.

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(`${outDir}/开关插座灯具清单.xlsx`);
console.log('exported');
