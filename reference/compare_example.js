const fs = require('fs');
const vm = require('vm');

global.document = {
    getElementById: () => ({
        getContext: () => ({
            measureText: (text) => ({ width: text.length * 6 }),
            fillText: () => {}, strokeRect: () => {}, fillRect: () => {},
            beginPath: () => {}, moveTo: () => {}, lineTo: () => {},
            quadraticCurveTo: () => {}, stroke: () => {}, fill: () => {}, closePath: () => {}
        }),
        click: () => {}
    })
};
global.WebKit = false;
global.clickMarker_to1C = "";
global.guid_from1C = "";

const code = fs.readFileSync(__dirname + '/original_parser_fixed.js', 'utf-8');
vm.runInThisContext(code);

const sql = fs.readFileSync('/tmp/sql-query-analyzer/examples/example.sql', 'utf-8');
drawGraph(sql, true);

const jsResult = {
    nodeCount: nodeArrow.length,
    firstNode: nodeArrow[0] ? { name: nodeArrow[0].name, type: nodeArrow[0].type } : null,
    edgeCount: edgeArrow.length,
    dropCount: dropQueryArrow.length,
    nodes: nodeArrow.map(n => ({
        id: n.id,
        name: n.name,
        type: n.type,
        isUnionPart: n.isUnionPart,
        isStub: n.isStub,
        own_in_tables: n.own_in_tables.slice()
    })),
    edges: edgeArrow.map(e => ({
        out: e.out_node.name,
        in: e.in_node.name
    })),
    drops: dropQueryArrow.slice()
};

fs.writeFileSync('/tmp/sql-query-analyzer/reference/js_example_result.json', JSON.stringify(jsResult, null, 2), 'utf-8');
console.log('JS result saved');
