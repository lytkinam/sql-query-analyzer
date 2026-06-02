const fs = require('fs');
const vm = require('vm');

// Set up globals before running script
global.document = {
    getElementById: () => ({
        getContext: () => ({
            measureText: (text) => ({ width: text.length * 6 }),
            fillText: () => {},
            strokeRect: () => {},
            fillRect: () => {},
            beginPath: () => {},
            moveTo: () => {},
            lineTo: () => {},
            quadraticCurveTo: () => {},
            stroke: () => {},
            fill: () => {},
            closePath: () => {}
        }),
        click: () => {}
    })
};
global.WebKit = false;
global.clickMarker_to1C = "";
global.guid_from1C = "";

const code = fs.readFileSync(__dirname + '/original_parser_fixed.js', 'utf-8');
vm.runInThisContext(code);

console.log('Script executed, drawGraph exists:', typeof drawGraph !== 'undefined');

const sql = 'ВЫБРАТЬ * ИЗ Справочник.Номенклатура КАК Т1 ВНУТРЕННЕЕ СОЕДИНЕНИЕ РегистрНакопления.Остатки КАК Т2 ПО Т1.Ссылка = Т2.Номенклатура ОБЪЕДИНИТЬ ВСЕ ВЫБРАТЬ * ИЗ Документ.Поступление КАК Т3';

drawGraph(sql, true);

console.log('JS nodeCount:', nodeArrow.length);
console.log('JS firstNode:', { name: nodeArrow[0].name, type: nodeArrow[0].type });
console.log('JS edgeCount:', edgeArrow.length);
console.log('JS dropCount:', dropQueryArrow.length);
console.log('JS nodes:');
nodeArrow.forEach(n => {
    console.log(`  id=${n.id} name=${n.name} type=${n.type} isUnionPart=${n.isUnionPart} isStub=${n.isStub} own_in_tables=[${n.own_in_tables.join(', ')}]`);
});
