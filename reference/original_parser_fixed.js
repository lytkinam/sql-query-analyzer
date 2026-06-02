
var WebKit = false;
var nodeArrowJSON_To1C;
var clickMarker_to1C = "";
var guid_from1C = "";

var node_text_padding = 4;
var sub_node_margin_left = 30;
var sub_node_margin_right = 10;
var sub_node_margin_bottom = 10;
var text_height = 12;
var font_family = "Arial";
var radius = 10;
var line_radius = 4;
var node_color = "#DAFFFF";
var node_border_color = "#BBD0E8";
var clicked_node_color = "#D5FFCB";
var clicked_node_border_color = "#FF0000";
var clicked_linked_node_color = "#AEFCC0";
var clicked_linked_edge_color = "#007929";
var selected_node_color = "#BBD0E8";
var selected_node_border_color = "#BBD0E8";
var selected_edge_color = "#A2B5C9";
var edge_line_color = "#2D3538";
var node_text_color = "#000000";
var clicked_node_text_color = "#000000";
var background_color = "#FFFFFF";
var node_border_width = 2;
var graph_vertical_margin = 10;
var graph_horizontal_margin = 20;
var node_horizontal_margin = 10;
var node_vertical_margin = 15;
var head_height = 5;
var edge_line_width = 1;
var edge_line_distance = 7;
var arrow_head_width = 6;
var arrow_head_length = 9;

var nodeArrow = [];
var edgeArrow = [];
var levelArrow = [];
var edgeNettoArrow = [];
var quotationMarkIDArrow = [];
var quotationMarkTextArrow = [];
var ctx;
var canvas;
var graph_height = 0;
var graph_length = 0;
var selectedEdgesArrow = [];
var selectedNodesArrow = [];
var overhangNode = null;
var clickedNode = null;
var clickedLinkedNodeArrow = [];
var clickedLinkedEdgesArrow = [];
var detailedScheme = false;
var dropQueryArrow = [];

var canvasLeft = "";
function ControlPoint(x, y, direction, rad) {
    this.x = x;
    this.y = y;
    this.lastDirection = direction;
    this.rad = rad;
}
function Node(id, name, text, type) {
    this.id = id;
    this.name = name;
    this.text = text;
    this.type = type;
    this.children = [];
    this.parent = null;
    this.max_parent = null;
    this.length = 0;
    this.height = 0;
    this.max_child_length = 0;
    this.x = 0;
    this.y = 0;
    this.isStub = false;
    this.level = null;
    this.own_in_tables = [];
    this.textHTML = "";
    this.isUnionPart = false;
    this.cornerStyle = "rounded";
    this.reconstructArrow = [];
    this.reconstructText = "";
}
Node.prototype.getNodeUpArrow = function() {
    clickedLinkedEdgesArrow = [];
    var freshArrow = [this];
    var upArrow = [];
    while (true) {
        freshArrow = getNodesExtendedWithAllChildrens(freshArrow);
        var topArrow = [];
        for (var i = 0; i < edgeNettoArrow.length; i++) {
            if (freshArrow.indexOf(edgeNettoArrow[i].in_node) >= 0) {
				if(topArrow.indexOf(edgeNettoArrow[i].out_node) < 0) {
                	topArrow.push(edgeNettoArrow[i].out_node);
                }
                clickedLinkedEdgesArrow.push(edgeNettoArrow[i]);
            }
        }
        upArrow = upArrow.concat(freshArrow);
        if (topArrow.length === 0) {
            break;
        }
        for (var i = 0; i < topArrow.length; i++) {
            var ind;
            while (upArrow.indexOf(topArrow[i]) > 0) {
                ind = upArrow.indexOf(topArrow[i]);
                upArrow.splice(ind, 1);
            }
        }
        freshArrow = topArrow;
    }
    return upArrow;
};
Node.prototype.setDimensions = function() {
    if (this.children.length > 0) {
        var max_child_length = 0;
        var sum_child_height = 0;
         for (var i = 0, max = this.children.length; i < max; i++) {
            this.children[i].setDimensions();
            max_child_length = Math.max(max_child_length, this.children[i].length);
            sum_child_height = sum_child_height + this.children[i].height;
            if (!this.children[i].isUnionPart) {
                sum_child_height += sub_node_margin_bottom;
            }
        }
        if (this.children.length > 1 && this.children[0].isUnionPart) {
            sum_child_height += sub_node_margin_bottom;
        }
        var own_length = ctx.measureText(this.name).width + node_text_padding * 2;
        var child_length = max_child_length + sub_node_margin_left + sub_node_margin_right;
        this.length = Math.max(own_length, child_length) + node_border_width * 2;
        this.height = text_height + node_text_padding * 2 + sum_child_height + sub_node_margin_bottom + node_border_width * 2;
        this.max_child_length = Math.max(own_length - sub_node_margin_left - sub_node_margin_right, max_child_length);
    } else {
        this.length = ctx.measureText(this.name).width + node_text_padding * 2 + node_border_width * 2;
        this.height = text_height + node_text_padding * 2 + node_border_width * 2;
    }
};
Node.prototype.alignDimensions = function() {
    if (this.parent !== null) {
        this.length = this.parent.max_child_length;
    }
};
Node.prototype.setCoordinates = function(x, y) {
    this.x = x;
    this.y = y;
    var child_y = y + text_height + node_text_padding * 2 + sub_node_margin_bottom + node_border_width * 2;
    for (var i = 0; i < this.children.length; i++) {
        this.children[i].setCoordinates(x + sub_node_margin_left, child_y);
        child_y += this.children[i].height;
        if (!this.children[i].isUnionPart) {
            child_y += sub_node_margin_bottom;
        }
    }
};
Node.prototype.draw = function() {
    var nodeColor;
    var border_color;
    var textColor;
    var style = "common";
    if(this === clickedNode) {
        style = "clicked";
    }
    else if(clickedLinkedNodeArrow.indexOf(this) >= 0) {
        style = "clickedLinked";
    }
    if(selectedNodesArrow.indexOf(this) >= 0) {
        style = "selected";
    }
        
    if(style === "common") {
        nodeColor = node_color;
        border_color = node_border_color;
        textColor = node_text_color;
    }
    else if(style === "selected") {
        nodeColor = selected_node_color;
        border_color = selected_node_border_color;
        textColor = node_text_color;
    }
    else if(style === "clicked") {
        nodeColor = clicked_node_color;
        border_color = clicked_node_border_color;
        textColor = clicked_node_text_color;
    }
    else if(style === "clickedLinked") {
        nodeColor = clicked_linked_node_color;
        border_color = node_border_color;
        textColor = node_text_color;
    }
        
    drawRoundedRectangl(this.x, this.y, this.length, this.height, radius, nodeColor, border_color, this.cornerStyle);
    ctx.fillStyle = textColor;
    ctx.textBaseline = "top";
    ctx.fillText(this.name, this.x + node_text_padding + node_border_width, this.y + node_text_padding);
    for (var i = 0; i < this.children.length; i++) {
        this.children[i].draw();
    }
};
function Edge(out_node, in_node) {
    this.out_node = out_node;
    this.in_node = in_node;
    this.controlPointArrow = [];
}
Edge.prototype.startLinea = function(Point) {
    this.controlPointArrow.push(Point);
};
Edge.prototype.moveDown = function(y) {
    var lastPoint = this.controlPointArrow[this.controlPointArrow.length - 1];
    var rad = Math.min(line_radius, (y - lastPoint.y) / 2);
    this.controlPointArrow.push(new ControlPoint(lastPoint.x, y, "down", rad));
    if(rad < line_radius) {
        lastPoint.rad = rad;
    }
};
Edge.prototype.moveAside = function(x) {
    var lastPoint = this.controlPointArrow[this.controlPointArrow.length - 1];
    var direction;
    var rad = Math.min(line_radius, Math.abs(x - lastPoint.x) / 2);
    if((x - lastPoint.x) > 0) {
        direction = "right";
    }
    else {
        direction = "left";
    }
    this.controlPointArrow.push(new ControlPoint(x, lastPoint.y, direction, rad));
    if(rad < line_radius) {
        lastPoint.rad = rad;
    }
};
Edge.prototype.getCurrentPoint = function() {
    return this.controlPointArrow[this.controlPointArrow.length - 1];
};
Edge.prototype.drawLine = function(clean) {
    if (clean === undefined) {
        clean = false;
    }
    if(!clean) {
        this.drawLine(true);
        clean = false;
    }
        
    var style = "common";
    if(clickedLinkedEdgesArrow.indexOf(this) >= 0) {
        style = "clickedLinked";
    }
    if(selectedEdgesArrow.indexOf(this) >= 0) {
        style = "selected";
    }
    if(clean) {
        style = "clean";
    }
        
    var lineColor;
    if(style === "common") {
        lineColor = edge_line_color;
    }
    else if(style === "selected") {
        lineColor = selected_edge_color;
    }
    else if(style === "clickedLinked") {
        lineColor = clicked_linked_edge_color;
    }
    else if(style === "clean") {
        lineColor = background_color;
    }
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = edge_line_width;
    ctx.beginPath();
    var currentPoint = this.controlPointArrow[0];
    ctx.moveTo(currentPoint.x, currentPoint.y);
    for (var i = 1; i < this.controlPointArrow.length - 1; i++) {
        currentPoint = this.controlPointArrow[i];
        var nextPoint = this.controlPointArrow[i + 1];
        if(currentPoint.lastDirection === "left") {
            ctx.lineTo(currentPoint.x + currentPoint.rad, currentPoint.y);
            ctx.quadraticCurveTo(currentPoint.x, currentPoint.y, currentPoint.x, currentPoint.y + currentPoint.rad);
        }
        else if(currentPoint.lastDirection === "right") {
            ctx.lineTo(currentPoint.x - currentPoint.rad, currentPoint.y);
            ctx.quadraticCurveTo(currentPoint.x, currentPoint.y, currentPoint.x, currentPoint.y + currentPoint.rad);
        }
        else {
            if(nextPoint.lastDirection === "left") {
                ctx.lineTo(currentPoint.x, currentPoint.y - currentPoint.rad);
                ctx.quadraticCurveTo(currentPoint.x, currentPoint.y, currentPoint.x - currentPoint.rad, currentPoint.y);
            }
            else {
                ctx.lineTo(currentPoint.x, currentPoint.y - currentPoint.rad);
                ctx.quadraticCurveTo(currentPoint.x, currentPoint.y, currentPoint.x + currentPoint.rad, currentPoint.y);
            }
        }
    }
    var currentPoint = this.controlPointArrow[this.controlPointArrow.length - 1];
    ctx.lineTo(currentPoint.x, currentPoint.y);
    ctx.stroke();
    ctx.fillStyle = lineColor;
    ctx.beginPath();
    var lastPoint = this.controlPointArrow[this.controlPointArrow.length - 1];
    if(lastPoint.lastDirection === "down") {
        ctx.moveTo(lastPoint.x, lastPoint.y);
        ctx.lineTo(lastPoint.x - arrow_head_width / 2, lastPoint.y - arrow_head_length);
        ctx.lineTo(lastPoint.x + arrow_head_width / 2, lastPoint.y - arrow_head_length);
    }
    else {
        ctx.moveTo(lastPoint.x, lastPoint.y);
        ctx.lineTo(lastPoint.x + arrow_head_length, lastPoint.y - arrow_head_width / 2);
        ctx.lineTo(lastPoint.x + arrow_head_length, lastPoint.y + arrow_head_width / 2);
    }
    ctx.closePath();
    ctx.fill();
};
function NodeLevel(nodes) {
    this.id = 0;
    this.nodes = nodes;
    this.x = 0;
    this.y = 0;
    this.height = 0;
    this.length = 0;
    this.horizontalChannel = null;
    this.verticalChannelArrow = [];
}
NodeLevel.prototype.setChannels = function() {
    this.horizontalChannel = new HorizontalChannel(this.y + this.height + node_vertical_margin / 2);
    this.verticalChannelArrow.push(new VerticalChannel(this.x - graph_horizontal_margin / 2));
    for (var i = 0; i < this.nodes.length - 1; i++) {
        this.verticalChannelArrow.push(new VerticalChannel(this.nodes[i].x + this.nodes[i].length + node_horizontal_margin / 2));
    }
    this.verticalChannelArrow.push(new VerticalChannel(this.nodes[i].x + this.nodes[i].length + graph_horizontal_margin / 2));
};
NodeLevel.prototype.resetChannelsCoordinates = function() {
    this.horizontalChannel.y = this.y + this.height + node_vertical_margin / 2;
    this.verticalChannelArrow[0].x = this.x - graph_horizontal_margin / 2;
    for (var i = 0; i < this.nodes.length - 1; i++) {
        this.verticalChannelArrow[i + 1].x = this.nodes[i].x + this.nodes[i].length + node_horizontal_margin / 2;
    }
    this.verticalChannelArrow[this.nodes.length].x = this.x + this.length + graph_horizontal_margin / 2
    - this.verticalChannelArrow[this.nodes.length].edgeArrow.length * (edge_line_distance + edge_line_width);
};
NodeLevel.prototype.findNearestVerticalChannel = function(x) {
    var min = Math.abs(x - this.verticalChannelArrow[0].x);
    var nearestChannel = this.verticalChannelArrow[0];
    for (var k = 0; k < this.verticalChannelArrow.length; k++) {
        if(Math.abs(x - this.verticalChannelArrow[k].x) < min) {
            min = Math.abs(x - this.verticalChannelArrow[k].x);
            nearestChannel = this.verticalChannelArrow[k];
        }
    }
    return nearestChannel;
};
NodeLevel.prototype.findBindingVerticalChannel = function(edge) {
    for (var i = 0; i < this.verticalChannelArrow.length; i++) {
        if(this.verticalChannelArrow[i].edgeArrow.indexOf(edge) >= 0) {
            return this.verticalChannelArrow[i];
        }
    }
    return null;
};
NodeLevel.prototype.findBindingHorizontalTrackIndex = function(edge) {
    for (var i = 0; i < this.horizontalChannel.trackArrow.length; i++) {
        if(this.horizontalChannel.trackArrow[i].indexOf(edge) >= 0) {
            return i;
        }
    }
    return -1;
};
function Segment(x1, x2, edge) {
    this.x1 = x1;
    this.x2 = x2;
    this.edge = edge;
}
Segment.prototype.overlaps = function(segment) {
    if(Math.max(this.x1, this.x2) <= Math.min(segment.x1, segment.x2)) {
        return false;
    }
    else if(Math.min(this.x1, this.x2) >= Math.max(segment.x1, segment.x2)) {
        return false;
    }
    else {
        return true;
    }
};
function HorizontalChannel(y) {
    this.y = y;
    this.segmentArrow = [];
    this.trackArrow = [];
}
function VerticalChannel(x) {
    this.x = x;
    this.edgeArrow = [];
}
function tableNameReplacer(str, p1) {
    return p1;
}
function getOwnInTables(text) {
	var isBracketFind = true;
    while(isBracketFind) {
        isBracketFind = false;
        if(text.search(/\(([^\(\)])*\)/gi) >= 0) {
            isBracketFind = true;
            text = text.replace(/\(([^\(\)])*\)/gi, " ~ ");
        }
    }
	var isSquareBracketFind = true;
    while(isSquareBracketFind) {
        isSquareBracketFind = false;
        if(text.search(/\[([^\[\]])*\]/gi) >= 0) {
            isSquareBracketFind = true;
            text = text.replace(/\[([^\[\]])*\]/gi, " ");
        }
    }
    var isCurlyBracketFind = true;
    while(isCurlyBracketFind) {
        isCurlyBracketFind = false;
        if(text.search(/{(?!(\s*\S+\s+(СОЕДИНЕНИЕ|JOIN)\s))([^}{])*}/gi) >= 0) {
            isCurlyBracketFind = true;
            text = text.replace(/{(?!(\s*\S+\s+(СОЕДИНЕНИЕ|JOIN)\s))([^}{])*}/gi, " ");
        }
    }
	text = text.replace(/(\s|^)(ОБЪЕДИНИТЬ|UNION)(\s+(ВСЕ|ALL))?($|\s)/gi," ! ");
	text = text.replace(/(\s|^)(ВЫБРАТЬ|SELECT)\s([^!])*(^|\s)(ИЗ|FROM)\s/gi,"ИЗ ");
    
    text = text.replace(/(\s|^)(СГРУППИРОВАТЬ|GROUP)\s[^!]*!/gi, " ");
	text = text.replace(/(\s|^)(ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE)\s[^!]*!/gi, " ");
	
	text = text.replace(/(\s|^)(СГРУППИРОВАТЬ|GROUP)\s(\s|\S)*$/gi, " ");
	text = text.replace(/(\s|^)(ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE)\s(\s|\S)*$/gi, " ");
	
	text = text.replace(/(\s|^)(ИНДЕКСИРОВАТЬ|INDEX)\s(\s|\S)*$/gi, " ");
 	text = text.replace(/(\s|^)(УПОРЯДОЧИТЬ|ORDER)\s(\s|\S)*$/gi, " ");
	text = text.replace(/(\s|^)(ИТОГИ|TOTALS)\s(\s|\S)*$/gi, " ");
	
    var own_in_tables = text.match(/(((\s|^)(ИЗ|FROM|СОЕДИНЕНИЕ|JOIN)\s+)|(,\s*))\S+(\s|$)/gim);
    if(own_in_tables === null) {
		own_in_tables = [];
	}
	for(var i = 0; i < own_in_tables.length; i++) {
        own_in_tables[i] = own_in_tables[i].replace(/(?:(?:(?:\s|^)(?:ИЗ|FROM|СОЕДИНЕНИЕ|JOIN)\s+)|(?:,\s*))(\S+)(?:\s|$)/gi, tableNameReplacer).toUpperCase();
    }
    var result = [];
    for(var i = 0; i < own_in_tables.length; i++) {
        if(result.indexOf(own_in_tables[i]) < 0) {
            result.push(own_in_tables[i]);
        }
    }
    return result;
}
function setNodeArrow() {
    function splitUnion(str) {
        var subUnionQueryArrow = str.split(/((?:^|\s)(?:ОБЪЕДИНИТЬ|UNION)\s+(?:ВСЕ|ALL)?(?:\s|^)+)/im);
        if (detailedScheme && subUnionQueryArrow.length > 1) {
            var superUnionNode = subNode;
            var superUnionText = "";
            var superUnionTextHTML = "";
            var unionPartCount = 0;
            var reconstructText = str;
            for (var u = 0; u < subUnionQueryArrow.length; u++) {
                if (subUnionQueryArrow[u].search(/((?:^|\s)(?:ОБЪЕДИНИТЬ|UNION)\s+(?:ВСЕ|ALL)?(?:\s|^)+)/im) === -1) {
                    subNode = new Node(idCount++, "Часть_" + ++unionPartCount, "", "sub_query");
                    subNode.isUnionPart = true;
                    
                    var union_str = subUnionQueryArrow[u];
                    reconstructArrow.push([subNode.id, union_str]);

                    subNode.text = union_str.replace(/~\d+~/g, deReplacer);
                    subNode.textHTML = union_str.replace(/~\d+~/g, deReplacerHTML);
                    superUnionText += subNode.text;
                    superUnionTextHTML += "" +
"<div id = 'subq" + subNode.id + "' class = 'subQueryBrief' onclick='onClickSubQuery[this]'>" + subNode.name + "</div>";
                    if (u === 0) {
                        subNode.cornerStyle = "bottomAngle";
                    }
                    else if (u === subUnionQueryArrow.length - 1) {
                        subNode.cornerStyle = "topAngle";
                    }
                    else {
                        subNode.cornerStyle = "allAngle";
                    }
                    if (superUnionNode.type === "sub_query") {
                        if (u === 0) {
                            subNode.text = subNode.text.replace(/^\s*\(/, "");
                            subNode.textHTML = subNode.textHTML.replace(/^\s*\(/, "");
                        }
                        else if (u === subUnionQueryArrow.length - 1) {
                            subNode.text = subNode.text.replace(/\s*\)(?!([\S\s]*[\(\)][\S\s]*))[\S\s]*/g, "");
                            subNode.textHTML = subNode.textHTML.replace(/\s*\)(?!([\S\s]*[\(\)][\S\s]*))[\S\s]*/g, "");
						}
                    }
                    subNode.own_in_tables = getOwnInTables(subNode.text.replace(/^\(/,"").replace(/\)(\s+(КАК|AS)\s+[^\s\)]+)?\s*$/,""));
                    nodeArrow.push(subNode);
                    reconstructText = reconstructText.replace(union_str, "~" + subNode.id + "~");
                    
                    superUnionNode.children.push(subNode);
                    subNode = superUnionNode;
                }                    
                else {
                    superUnionText += subUnionQueryArrow[u];
                    superUnionTextHTML += "" +
"<div class = 'unionSeparator'>" + subUnionQueryArrow[u] + "</div>";
                }
            }
            superUnionNode.text = superUnionText;
            superUnionNode.textHTML = superUnionTextHTML;
            reconstructArrow.push([superUnionNode.id, reconstructText]);
        }
        else {
            subNode.text = str.replace(/~\d+~/g, deReplacer);
            subNode.textHTML = str.replace(/~\d+~/g, deReplacerHTML);
            subNode.own_in_tables = getOwnInTables(subNode.text.replace(/^\(/,"").replace(/\)(\s+(КАК|AS)\s+[^\s\)]+)?\s*$/,""));
            reconstructArrow.push([subNode.id, str]);
        }
        
    }
    function replacer(str, p1) {
        isFind = true;
        var subNode_id = idCount++;
        if(p1 === undefined) {
            p1 = "Подзапрос_" + (++unnamedSubQueryCount);
        }
        subNode = new Node(subNode_id, p1, "", "sub_query");
        nodeArrow.push(subNode);
        splitUnion(str);
        return "~" + subNode_id + "~";
    }
    function deReplacer(sub_str) {
        var sub_ind = parseInt(sub_str.replace("~", ""));
        subNode.children.push(nodeArrow[sub_ind]);
        return nodeArrow[sub_ind].text;
    }
    function deReplacerHTML(sub_str) {
        var sub_ind = parseInt(sub_str.replace("~", ""));
        return "" +
"<div id = 'subq" + sub_ind + "' class = 'subQueryBrief' onclick='onClickSubQuery[this]'>" + nodeArrow[sub_ind].name + "</div>";
    }
    
    sql_text = sql_text.replace(/\/\/.*/g, "");// выкидываем комментарии из запросов
    // сначала убираем весь текст в кавычках, сохраняем его в отдельный мссив
    var quotationMarkIsFind = true;
    function quotationMarkReplacer(str) {
        quotationMarkIsFind = true;
        quotationMarkTextArrow.push(str);
        var guid = getGUID();
        quotationMarkIDArrow.push(guid);
        return guid;
    }
    while(quotationMarkIsFind) {
        quotationMarkIsFind = false;
        sql_text = sql_text.replace(/"[^"]*"/i, quotationMarkReplacer);
	}
	
    var queryTextArrow = sql_text.split(";");
    nodeArrow = [];
    dropQueryArrow = [];
    var rezultTableCount = 0;
    var unnamedSubQueryCount = 0;
    var idCount = 0;
    for (var ind in queryTextArrow) {
        var sub_sql_text = queryTextArrow[ind].trim();
        if(sub_sql_text.search(/(^|\s)(УНИЧТОЖИТЬ|DROP)\s+/i) >= 0) {
            dropQueryArrow.push(sub_sql_text.replace(/(^|\s)(УНИЧТОЖИТЬ|DROP)\s+/i, "").trim());
            continue;
        }
        var reconstructArrow = [];
        var matchArrow = sub_sql_text.match(/(\s(ПОМЕСТИТЬ|INTO)\s+)(\S+($|\s))/gi);
        var table_id = idCount++;
        var tableName = "";
        var tableType = "";
        if (matchArrow === null) {
            tableName = "Результат_" + (++rezultTableCount);
            tableType = "result";
        } else {
            tableName = matchArrow[0].replace(/(ПОМЕСТИТЬ|INTO)/i, "").trim();
            tableType = "temp_query";
        }
        var node = new Node(table_id, tableName, sub_sql_text, tableType);
        nodeArrow.push(node);
        
        // заменяем круглые скобки на квадратные кроме скобок вложенных запросов
        var isFindBrackets = true;
        function bracketsReplacer(str) {
            isFindBrackets = true;
            return str.replace(/\(/g, "[").replace(/\)/g, "]");
        }
        while (isFindBrackets) {
            isFindBrackets = false;
            sub_sql_text = sub_sql_text.replace(/\((?!\s*(ВЫБРАТЬ|SELECT)\s)([^\(\)])*\)/gi, bracketsReplacer);
        }
        // разбираем вложенные запросы
        var isFind = true;
        var subNode;
        
        while (isFind) {
            isFind = false;
            sub_sql_text = sub_sql_text.replace(/\(\s*(?:ВЫБРАТЬ|SELECT)\s[^\(\)]*\)\s*(?:(?:КАК|AS)\s+([^\s\)]+)(?=(?:\s|$|\))))?/i, replacer);
            isFindBrackets = true;
            while (isFindBrackets) {
            	isFindBrackets = false;
            	sub_sql_text = sub_sql_text.replace(/\((?!\s*(ВЫБРАТЬ|SELECT)\s)([^\(\)])*\)/gi, bracketsReplacer);
        	}
        }
        subNode = node;
        splitUnion(sub_sql_text);
        node = subNode;
        node.reconstructArrow = reconstructArrow;
    }
    //убираем лишние хвосты и начальные скобки в тексте временных запросов
    for (var i = 0, max = nodeArrow.length; i < max; i++) {
        if (nodeArrow[i].type === "sub_query" && !nodeArrow[i].isUnionPart) {
            nodeArrow[i].text = nodeArrow[i].text.replace(/^\s*\(/, "").replace(/\s*\)(?!([\S\s]*[\(\)][\S\s]*))[\S\s]*/g, "");
            nodeArrow[i].textHTML = nodeArrow[i].textHTML.replace(/^\s*\(/, "").replace(/\s*\)(?!([\S\s]*[\(\)][\S\s]*))[\S\s]*/g, "");
        }
        nodeArrow[i].text = nodeArrow[i].text.replace(/\[/g, "(").replace(/\]/g, ")");
        nodeArrow[i].textHTML = nodeArrow[i].textHTML.replace(/\[/g, "(").replace(/\]/g, ")");
    }
    // проставляем родителей
    for (var i = 0; i < nodeArrow.length; i++) {
        for (var j = 0; j < nodeArrow[i].children.length; j++) {
            nodeArrow[i].children[j].parent = nodeArrow[i];
		}
    }
    for (var i = 0; i < nodeArrow.length; i++) {
        if(nodeArrow[i].type !== "sub_query") {
            var max_parent = nodeArrow[i];
            var successorArrow = [max_parent];
            while(successorArrow.length > 0) {
                if(successorArrow[0].children.length > 0) {
                    for (var j = 0; j < successorArrow[0].children.length; j++) {
                        successorArrow.push(successorArrow[0].children[j]);
                    }
                }
                successorArrow[0].max_parent = max_parent;
                successorArrow.splice(0, 1);
            }
        }
    }
    // возвращаем текст который был в кавычках
    for (var i = 0; i < nodeArrow.length; i++) {
        for(var j = 0; j < quotationMarkIDArrow.length; j++) {
            nodeArrow[i].text = nodeArrow[i].text.replace(quotationMarkIDArrow[j], quotationMarkTextArrow[j]);
            nodeArrow[i].textHTML = nodeArrow[i].textHTML.replace(quotationMarkIDArrow[j], getStringValueForHTML(quotationMarkTextArrow[j]));
        }
    }
}
function setEdgeArrow() {
    var isFindBrackets = true;
    function bracketsReplacer(str) {
        isFindBrackets = true;
        return str.replace(/\(/g, "[").replace(/\)/g, "]");
    }
    edgeNettoArrow = [];
    edgeArrow = [];
    for (var i = 0; i < nodeArrow.length; i++) {
        if (nodeArrow[i].type === "temp_query") {
            var nodeHasOutEdges = false;
            for (var j = 0; j < nodeArrow.length; j++) {
                if (nodeArrow[j].own_in_tables.indexOf(nodeArrow[i].name.toUpperCase()) >= 0) {
                    edgeNettoArrow.push(new Edge(nodeArrow[i], nodeArrow[j]));
                    nodeHasOutEdges = true;
                }
           }
            nodeArrow[i].isStub = ! nodeHasOutEdges;
        }
    }
	function setNodeEdgeArrow(node) {
		var nodeEdgeArrow = [];
		var nodeComingNodes = [];
		for(var i = 0; i < edgeNettoArrow.length; i++) {
			if(edgeNettoArrow[i].in_node === node) {
				nodeEdgeArrow.push(edgeNettoArrow[i]);
				nodeComingNodes.push(edgeNettoArrow[i].out_node);
			}
		}
		for(var i = 0; i < node.children.length; i++) {
			setNodeEdgeArrow(node.children[i]);
			for(var j = 0; j < edgeArrow.length; j++) {
				if(edgeArrow[j].in_node === node.children[i]) {
					if(nodeComingNodes.indexOf(edgeArrow[j].out_node) < 0) {
					    nodeEdgeArrow.push(new Edge(edgeArrow[j].out_node, node));
					    nodeComingNodes.push(edgeArrow[j].out_node);
					}
				}
			}
		}
		edgeArrow = edgeArrow.concat(nodeEdgeArrow);
	}
	for(var i = 0; i < nodeArrow.length; i++) {
        if (nodeArrow[i].type !== "sub_query") {
			setNodeEdgeArrow(nodeArrow[i]);
		}
	}
}
function setNodeDimentions() {
    for (var i = 0; i < nodeArrow.length; i++) {
        if (nodeArrow[i].type !== "sub_query") {
            nodeArrow[i].setDimensions();
        }
    }
    for (var i = 0; i < nodeArrow.length; i++) {
        if (nodeArrow[i].type === "sub_query") {
            nodeArrow[i].alignDimensions();
        }
    }
}
function setLevelArrow() {
    levelArrow = [];
    var freshArrow = [];
    for (var i = 0, max = nodeArrow.length; i < max; i++) {
        if (nodeArrow[i].type === "result" || (nodeArrow[i].type === "temp_query" && nodeArrow[i].isStub)) {
            freshArrow.push(nodeArrow[i]);
        }
    }
    while (true) {
        topArrow = [];
        for (i = 0; i < edgeArrow.length; i++) {
            if (freshArrow.indexOf(edgeArrow[i].in_node) >= 0) {
                if(topArrow.indexOf(edgeArrow[i].out_node) < 0) {
                    topArrow.push(edgeArrow[i].out_node);
                }
            }
        }
        levelArrow.push(new NodeLevel(freshArrow.slice()));
        if (topArrow.length === 0) {
            break;
        }
        for (i = 0; i < topArrow.length; i++) {
            for (var j = 0; j < levelArrow.length; j++) {
                var ind;
                while (levelArrow[j].nodes.indexOf(topArrow[i]) >= 0) {
                    ind = levelArrow[j].nodes.indexOf(topArrow[i]);
                    levelArrow[j].nodes.splice(ind, 1);
                }
                if (levelArrow[j].nodes.length === 0 ) {
                    levelArrow.splice(j, 1);
                    j--;
                }
            }
        }
        freshArrow = topArrow;
    }
}
function setLevelDimensions() {
    graph_height = 0;
    graph_length = 0;
    for (var i = 0; i < levelArrow.length; i++) {
        levelArrow[i].id = i;
        var length = 0;
        var height = 0;
        for (var j = 0; j < levelArrow[i].nodes.length; j++) {
            levelArrow[i].nodes[j].level = levelArrow[i];
            height = Math.max(height, levelArrow[i].nodes[j].height);
            length += node_horizontal_margin + levelArrow[i].nodes[j].length;
        }
        if (length > 0) {
            length -= node_horizontal_margin;
        }
        levelArrow[i].length = length;
        levelArrow[i].height = height;
        graph_length = Math.max(length, graph_length);
        graph_height += height + node_vertical_margin;
    }
    if (graph_height > 0) {
        graph_height -= node_vertical_margin;
    }
}
function setNodeCoordinates() {
    var horizontal_center = graph_horizontal_margin + graph_length / 2;
    var level_y = head_height + graph_vertical_margin;
    for (var i = levelArrow.length - 1; i >= 0; i--) {
        var level_x = horizontal_center - levelArrow[i].length / 2;
        levelArrow[i].x = level_x;
        levelArrow[i].y = level_y;
        for (var j = 0; j < levelArrow[i].nodes.length; j++) {
            if(levelArrow[i].verticalChannelArrow.length > 0) {
                level_x += levelArrow[i].verticalChannelArrow[j].edgeArrow.length * (edge_line_distance + edge_line_width);
            }
            levelArrow[i].nodes[j].setCoordinates(level_x, level_y);
            level_x += levelArrow[i].nodes[j].length + node_horizontal_margin;
        }
        level_y += levelArrow[i].height + node_vertical_margin;
        if(levelArrow[i].horizontalChannel !== null) {
            level_y += levelArrow[i].horizontalChannel.trackArrow.length * (edge_line_distance + edge_line_width);
        }
    }
}
function setGraphChannels() {
    for (var i = 0; i < levelArrow.length; i++) {
        levelArrow[i].setChannels();
    }
}
function bindEdgeToChannels() {
    for (var i = 0; i < edgeNettoArrow.length; i++) {
        var x1 = edgeNettoArrow[i].out_node.x + edgeNettoArrow[i].out_node.length / 2;
        var x2;
        var horizontalChannel = edgeNettoArrow[i].out_node.level.horizontalChannel;
        var nearestChannel;
        for (var j = edgeNettoArrow[i].out_node.level.id - 1; j > edgeNettoArrow[i].in_node.max_parent.level.id; j--) {
            nearestChannel = levelArrow[j].findNearestVerticalChannel(x1);
            nearestChannel.edgeArrow.push(edgeNettoArrow[i]);
            x2 = nearestChannel.x;
            horizontalChannel.segmentArrow.push(new Segment(x1, x2, edgeNettoArrow[i]));
            x1 = x2;
            horizontalChannel = levelArrow[j].horizontalChannel;
        }
        if(edgeNettoArrow[i].in_node.type === "sub_query") {
            nearestChannelID = edgeNettoArrow[i].in_node.max_parent.level.nodes.indexOf(edgeNettoArrow[i].in_node.max_parent) + 1;
			nearestChannel = edgeNettoArrow[i].in_node.max_parent.level.verticalChannelArrow[nearestChannelID];
            nearestChannel.edgeArrow.unshift(edgeNettoArrow[i]);
            x2 = nearestChannel.x;
            horizontalChannel.segmentArrow.push(new Segment(x1, x2, edgeNettoArrow[i]));
        }
        else {
            x2 = edgeNettoArrow[i].in_node.x + edgeNettoArrow[i].in_node.length / 2;
            horizontalChannel.segmentArrow.push(new Segment(x1, x2, edgeNettoArrow[i]));
        }
    }
    for (var i = 0; i < levelArrow.length; i++) {
        var segmentSqueezedArrow = [];
        var trackArrow = [];
        for (var j = 0; j < levelArrow[i].horizontalChannel.segmentArrow.length; j++) {
            var segment = levelArrow[i].horizontalChannel.segmentArrow[j];
            var overlapsAllSegments = true;
            for (var k = 0; k < segmentSqueezedArrow.length; k++) {
                var overlaps = false;
                for (var l = 0; l < segmentSqueezedArrow[k].length; l++) {
                    if(segment.overlaps(segmentSqueezedArrow[k][l])) {
                        overlaps = true;
                    }
                }
                if(!overlaps) {
                    overlapsAllSegments = false;
                    segmentSqueezedArrow[k].push(segment);
                    break;
                }
            }
            if(overlapsAllSegments) {
                segmentSqueezedArrow.push([segment]);
            }
        }
        for (var j = 0; j < segmentSqueezedArrow.length; j++) {
            trackArrow.push([]);
            for (var k = 0; k < segmentSqueezedArrow[j].length; k++) {
                trackArrow[j].push(segmentSqueezedArrow[j][k].edge);
            }
        }
        levelArrow[i].horizontalChannel.trackArrow = trackArrow;
    }
}
function extendLevelsDimensions() {
    graph_length = 0;
    for (var i = 0; i < levelArrow.length; i++) {
        var length = 0;
        for (var j = 0; j < levelArrow[i].verticalChannelArrow.length; j++) {
            length += levelArrow[i].verticalChannelArrow[j].edgeArrow.length * (edge_line_distance + edge_line_width);
        }
        levelArrow[i].length += length;
        graph_length = Math.max(levelArrow[i].length, graph_length);
        graph_height += levelArrow[i].horizontalChannel.trackArrow.length * (edge_line_distance + edge_line_width);
    }
}
function resetGraphChannelsCoordinates() {
    for (var i = 0; i < levelArrow.length; i++) {
        levelArrow[i].resetChannelsCoordinates();
    }
}
function setEdgeLines() {
    for (var i = 0; i < edgeNettoArrow.length; i++) {
        var bindingChannel;
        var point = new ControlPoint(edgeNettoArrow[i].out_node.x + edgeNettoArrow[i].out_node.length / 2, edgeNettoArrow[i].out_node.y + edgeNettoArrow[i].out_node.height);
        edgeNettoArrow[i].startLinea(point);
        var x;
        var indexOfEdge = edgeNettoArrow[i].out_node.level.findBindingHorizontalTrackIndex(edgeNettoArrow[i]);
        edgeNettoArrow[i].moveDown(edgeNettoArrow[i].out_node.level.horizontalChannel.y + (indexOfEdge + 0.5) * (edge_line_distance + edge_line_width));
        for (var j = edgeNettoArrow[i].out_node.level.id - 1; j > edgeNettoArrow[i].in_node.max_parent.level.id; j--) {
            bindingChannel = levelArrow[j].findBindingVerticalChannel(edgeNettoArrow[i]);
            x = bindingChannel.x + (bindingChannel.edgeArrow.indexOf(edgeNettoArrow[i]) + 0.5) * (edge_line_distance + edge_line_width);
            edgeNettoArrow[i].moveAside(x);
            indexOfEdge = levelArrow[j].findBindingHorizontalTrackIndex(edgeNettoArrow[i]);
            edgeNettoArrow[i].moveDown(levelArrow[j].horizontalChannel.y + (indexOfEdge + 0.5) * (edge_line_distance + edge_line_width));
        }
        if(edgeNettoArrow[i].in_node.type === "sub_query") {
            bindingChannel = edgeNettoArrow[i].in_node.max_parent.level.findBindingVerticalChannel(edgeNettoArrow[i], indexOfEdge);
            x = bindingChannel.x + (bindingChannel.edgeArrow.indexOf(edgeNettoArrow[i]) + 0.5) * (edge_line_distance + edge_line_width);
            edgeNettoArrow[i].moveAside(x);
            
            edgeNettoArrow[i].moveDown(edgeNettoArrow[i].in_node.y + edgeNettoArrow[i].in_node.height / 2);
            edgeNettoArrow[i].moveAside(edgeNettoArrow[i].in_node.x + edgeNettoArrow[i].in_node.length);
        }
        else {
            x = edgeNettoArrow[i].in_node.x + edgeNettoArrow[i].in_node.length / 2;
            edgeNettoArrow[i].moveAside(x);
            edgeNettoArrow[i].moveDown(edgeNettoArrow[i].in_node.y);
        }
    }
}
function setCanvas() {
    canvas.width = graph_horizontal_margin * 2 + graph_length;
    canvas.height = head_height + graph_vertical_margin * 2 + graph_height;
    ctx.strokeStyle = "black";
    ctx.strokeRect(0, 0, canvas.width, canvas.height);
    ctx.font = "" + text_height + "px " + font_family;
    ctx.fillStyle = background_color;
    ctx.fillRect(1, 1, canvas.width - 2, canvas.height - 2);
    canvas.onmousemove = onMouseMoveCanvas;
    canvas.onclick = onCanvasClick;
}
function drawNodes() {
    for (var i = 0; i < nodeArrow.length; i++) {
        if (nodeArrow[i].type !== "sub_query") {
            nodeArrow[i].draw();
        }
    }
}
function drawEdgeLines() {
    for (var i = 0; i < edgeNettoArrow.length; i++) {
        edgeNettoArrow[i].drawLine();
    }
}
function drawClickedEdgeLines() {
    for (var i = 0; i < clickedLinkedEdgesArrow.length; i++) {
        clickedLinkedEdgesArrow[i].drawLine();
    }
}
function drawGraph(text, detailed) {
    detailedScheme = detailed;
    clickedLinkedNodeArrow = [];
    clickedLinkedEdgesArrow = [];
    sql_text = text;
    canvas = document.getElementById("canvas");
    ctx = canvas.getContext('2d');
    ctx.font = "" + text_height + "px " + font_family;
    setNodeArrow();
    setEdgeArrow();
    setNodeDimentions();
    setLevelArrow();
    setLevelDimensions();
    setNodeCoordinates();
    setGraphChannels();
    bindEdgeToChannels();
    extendLevelsDimensions();
    setNodeCoordinates();
    resetGraphChannelsCoordinates();
    setEdgeLines();
    setCanvas();
    drawNodes();
    drawEdgeLines();
    var nodeArrowTo1C = [];
    for (var i = 0; i < nodeArrow.length; i++) {
        nodeArrowTo1C.push({name: nodeArrow[i].name, textHTML: nodeArrow[i].textHTML});
	    //if (detailedScheme) {
	    //    form1C.ПередатьУзелГрафаПодробный(nodeArrow[i].name, nodeArrow[i].textHTML);
	    //}
	    //else {
	    //    form1C.ПередатьУзелГрафа(nodeArrow[i].name, nodeArrow[i].textHTML);
	    //}
    }
    nodeArrowJSON_To1C = JSON.stringify(nodeArrowTo1C);
}
function drawRoundedRectangl(x, y, length, height, r, background_color, border_color, cornerStyle) {
    if (cornerStyle === undefined) {
        cornerStyle = "rounded";
    }
    r = Math.min(r, length / 2, height / 2);
    ctx.beginPath();
    
    if (cornerStyle === "topAngle" || cornerStyle === "allAngle") {
        ctx.moveTo(x, y);
    }
    else {
        ctx.moveTo(x + r, y);
    }
    
    if (cornerStyle === "topAngle" || cornerStyle === "allAngle") {
        ctx.lineTo(x + length, y);
    }
    else {
        ctx.lineTo(x + length - r, y);
    }
    
    if (cornerStyle === "bottomAngle" || cornerStyle === "rounded") {
        ctx.quadraticCurveTo(x + length, y, x + length, y + r);
    }
    
    if (cornerStyle === "bottomAngle" || cornerStyle === "allAngle") {
        ctx.lineTo(x + length, y + height);
    }
    else {
        ctx.lineTo(x + length, y + height - r);
    }
    
    if (cornerStyle === "topAngle" || cornerStyle === "rounded") {
        ctx.quadraticCurveTo(x + length, y + height, x + length - r, y + height);
    }
    
    if (cornerStyle === "bottomAngle" || cornerStyle === "allAngle") {
        ctx.lineTo(x, y + height);
    }
    else {
        ctx.lineTo(x + r, y + height);
    }
    
    if (cornerStyle === "topAngle" || cornerStyle === "rounded") {
        ctx.quadraticCurveTo(x, y + height, x, y + height - r);
    }
    
    if (cornerStyle === "topAngle" || cornerStyle === "allAngle") {
        ctx.lineTo(x, y);
    }
    else {
        ctx.lineTo(x, y + r);
    }
    
    if (cornerStyle === "bottomAngle" || cornerStyle === "rounded") {
        ctx.quadraticCurveTo(x, y, x + r, y);
    }
    
    ctx.lineWidth = node_border_width;
    ctx.strokeStyle = border_color;
    ctx.stroke();
    ctx.fillStyle = background_color;
    ctx.fill();
}
function getNodesExtendedWithAllChildrens(initialNodeArrow) {
    var childrenArrow = [];
    while(initialNodeArrow.length > 0) {
        if(initialNodeArrow[0].children.length > 0) {
            for (var i = 0; i < initialNodeArrow[0].children.length; i++) {
                initialNodeArrow.push(initialNodeArrow[0].children[i]);
            }
        }
        childrenArrow.push(initialNodeArrow[0]);
        initialNodeArrow.splice(0, 1);
    }
    return childrenArrow;
}
function getFullText(nodeUpArrow) {
    var text = "";
    if(nodeUpArrow.length > 0) {
        for (var i = 1; i < nodeUpArrow.length; i++) {
        	if (nodeUpArrow[i].type !== "sub_query") {
                text = nodeUpArrow[i].text + "\n;\n" + text;
            }
    	}
    }
    return text;
}
function onSelectEdgeLine(edge) {
    if(selectedEdgesArrow.indexOf(edge) < 0) {
        selectedEdgesArrow.push(edge);
        selectedNodesArrow.push(edge.in_node);
        selectedNodesArrow.push(edge.out_node);
        edge.in_node.draw();
        edge.out_node.draw();
    }
    drawEdgeLines();
    drawClickedEdgeLines();
    edge.drawLine();
}
function onNotSelectEdgeLine(edge) {
    var ind;
    if(selectedEdgesArrow.indexOf(edge)  >= 0) {
        ind = selectedEdgesArrow.indexOf(edge);
        selectedEdgesArrow.splice(ind, 1);
        if(selectedNodesArrow.indexOf(edge.in_node)  >= 0) {
            ind = selectedNodesArrow.indexOf(edge.in_node);
            selectedNodesArrow.splice(ind, 1);
        }
        if(selectedNodesArrow.indexOf(edge.out_node)  >= 0) {
            ind = selectedNodesArrow.indexOf(edge.out_node);
            selectedNodesArrow.splice(ind, 1);
        }
        if(selectedNodesArrow.indexOf(edge.in_node) < 0) {
            edge.in_node.draw();
        }
        if(selectedNodesArrow.indexOf(edge.out_node) < 0) {
            edge.out_node.draw();
        }
        drawEdgeLines();
        drawClickedEdgeLines();
    }
}
function onMouseMoveCanvas(evt) {
    var mouseX = 0;
    var mouseY = 0;
    if (WebKit) {
		var canvasRect = canvas.getBoundingClientRect()
	    mouseX = evt.pageX - canvasRect.left;
	    mouseY = evt.pageY - canvasRect.top;
    }
    else {
	    mouseX = evt.pageX - canvas.offsetLeft;
	    mouseY = evt.pageY - canvas.offsetTop;
    }
    // наведение на ребра графа
    for (var i = 0; i < edgeNettoArrow.length; i++) {
        var findEdge = false;
        for (var j = 0; j < edgeNettoArrow[i].controlPointArrow.length - 1; j++) {
            var x1 = Math.min(edgeNettoArrow[i].controlPointArrow[j].x, edgeNettoArrow[i].controlPointArrow[j + 1].x);
            var x2 = Math.max(edgeNettoArrow[i].controlPointArrow[j].x, edgeNettoArrow[i].controlPointArrow[j + 1].x);
            var y1 = Math.min(edgeNettoArrow[i].controlPointArrow[j].y, edgeNettoArrow[i].controlPointArrow[j + 1].y);
            var y2 = Math.max(edgeNettoArrow[i].controlPointArrow[j].y, edgeNettoArrow[i].controlPointArrow[j + 1].y);
            if(y1 === y2) {
                if(mouseX >= x1 && mouseX <= x2 && Math.abs(y1 - mouseY) <= 3){
                    onSelectEdgeLine(edgeNettoArrow[i]);
                    findEdge = true;
                }
            }
            else if(x1 === x2) {
                if(mouseY >= y1 && mouseY <= y2 && Math.abs(x1 - mouseX) <= 3){
                    onSelectEdgeLine(edgeNettoArrow[i]);
                    findEdge = true;
                }
            }
        }
        if(findEdge === false) {
            onNotSelectEdgeLine(edgeNettoArrow[i]);
        }
    }
    // наведение на узел
    var findNode = false;
    var overhangNodeArrow = [];
    for (var i = 0; i < nodeArrow.length; i++) {
        if(mouseX >= nodeArrow[i].x && mouseX <= (nodeArrow[i].x + nodeArrow[i].length) && mouseY >= nodeArrow[i].y && mouseY <= (nodeArrow[i].y + nodeArrow[i].height)) {
            this.style.cursor = 'pointer';
            overhangNodeArrow.push(nodeArrow[i]);
            findNode = true;
        }
    }
    if(findNode === true) {
        var maxNode = overhangNodeArrow[0];
        var max_x = maxNode.x;
	    for (var i = 1; i < overhangNodeArrow.length; i++) {
	        if(overhangNodeArrow[i].x > max_x) {
	            maxNode = overhangNodeArrow[i];
	            max_x = maxNode.x;
	        }
	    }
	    overhangNode = maxNode; 
    }
    else {
        this.style.cursor = 'auto';
        overhangNode = null;
    }
}
function getCleanText(text) {
    // сначала убираем весь текст в кавычках, сохраняем его в отдельный мссив
    var quotationMarkIDArrow_ = [];
    var quotationMarkTextArrow_ = [];
    var quotationMarkIsFind = true;
    function quotationMarkReplacer(str) {
        quotationMarkIsFind = true;
        quotationMarkTextArrow_.push(str);
        var guid = getGUID();
        quotationMarkIDArrow_.push(guid);
        return guid;
    }
    while(quotationMarkIsFind) {
        quotationMarkIsFind = false;
        text = text.replace(/"[^"]*"/i, quotationMarkReplacer);
	}
	
	text = text.replace(/(ПОМЕСТИТЬ|INTO)\s+\S+($|\s)/i, "");
	text = text.replace(/(^|\s)(ИНДЕКСИРОВАТЬ|INDEX)\s(\s|\S)*/ig, "");
	
    // возвращаем текст который был в кавычках
    for(var j = 0; j < quotationMarkIDArrow_.length; j++) {
        text = text.replace(quotationMarkIDArrow_[j], quotationMarkTextArrow_[j]);
    }
	
	return text;
}
var id_to1C = "";
var name_to1C = "";
var text_to1C = "";
var textHTML_to1C = "";
var cleanText_to1C = "";
var fullText_to1C = "";
function onCanvasClick() {
    if(overhangNode !== null) {
        clickedLinkedNodeArrow = overhangNode.getNodeUpArrow();
        drawNodes();
        drawEdgeLines();
        drawClickedEdgeLines();
		
		id_to1C = overhangNode.id;
		name_to1C = overhangNode.name;
		text_to1C = overhangNode.text;
		textHTML_to1C = overhangNode.textHTML;
		cleanText_to1C = getCleanText(overhangNode.text);
		fullText_to1C = getFullText(clickedLinkedNodeArrow);
	}
}
function clickNodeByText(text) {
	var node = null;
	for (var i = 0; i < nodeArrow.length; i++) {
	    if (nodeArrow[i].text === text) {
	        node = nodeArrow[i];
	        break;
	    }
	}
	if (node !== null) {
		overhangNode = node;
		onCanvasClick();
	}
}
//function setForm1C(form) {
//	form1C = form;
//}
//function getNodeArrow() {
//	return nodeArrow[0].text;
//}
function getGUID() {
	clickMarker_to1C = "ПолучитьУИ";
	document.getElementById("canvas").click();    
	clickMarker_to1C = "";
	return guid_from1C;
}
function getStringValueForHTML(stringValue) {
    var stringValueForHTML = "";
    for (var i = 0; i < stringValue.length; i++) {
        stringValueForHTML = stringValueForHTML + "&#" + stringValue.charCodeAt(i);
    }
    return stringValueForHTML;
}
function getReconstructQueryText(id, text) {
	var node = nodeArrow[id];
	var max_parent = node.max_parent;
	var max_parent_reconstructArrow = [];
	for (var i = 0; i < max_parent.reconstructArrow.length; i++) {
	    max_parent_reconstructArrow.push(max_parent.reconstructArrow[i].slice());
	}
	
    function deReplacer(sub_str) {
        var sub_ind = parseInt(sub_str.replace("~", ""));
        var rezult = "";
        for (var i = 0; i < max_parent_reconstructArrow.length; i++) {
            if (max_parent_reconstructArrow[i][0] === sub_ind) {
                rezult = max_parent_reconstructArrow[i][1];
                break;
            }
        }
        if (! nodeArrow[sub_ind].isUnionPart) {
            rezult = rezult.replace(/\(/g, "[").replace(/\)/g, "]");
        }
        return rezult;
    };
    function newTextReplacer(sub_str, p1) {
        return sub_str.replace(p1, text);
    };
    
	for (var i = 0; i < max_parent_reconstructArrow.length; i++) {
	    max_parent_reconstructArrow[i][1] = max_parent_reconstructArrow[i][1].replace(/~\d+~/g, deReplacer);
	    if (id === "" + max_parent_reconstructArrow[i][0]) {
	    	if (i === max_parent_reconstructArrow.length - 1) {
	    	    max_parent_reconstructArrow[i][1] = text;
	    	}
	    	else {
	     		max_parent_reconstructArrow[i][1] = max_parent_reconstructArrow[i][1].replace(/\(*([^\)]*)\)*[\s\S]*/i, newTextReplacer);
			}	
	    }
	}
	
	var max_parentText = max_parent_reconstructArrow[max_parent_reconstructArrow.length - 1][1].replace(/\[/g, "(").replace(/\]/g, ")");
    // возвращаем текст который был в кавычках
    for(var j = 0; j < quotationMarkIDArrow.length; j++) {
        max_parentText = max_parentText.replace(quotationMarkIDArrow[j], quotationMarkTextArrow[j]);
    }
    
	return getRecomposedText(max_parent, max_parentText, dropQueryArrow.slice());
}
function insertDropQueryText(g) {
	var tablesToInsertDropText = [];
	for (var i = 0; i < nodeArrow.length; i++) {
	    if (nodeArrow[i].type === "temp_query" && ! nodeArrow[i].isStub) {
	   		tablesToInsertDropText.push(nodeArrow[i].name);
	   	}
	}
	return getRecomposedText("", "", tablesToInsertDropText);
}
function getRecomposedText(nodeToReplace, textToReplace, tablesToInsertDropText) {
	var totalText = "";
	var restNodes = nodeArrow.slice();
	
	for (var i = levelArrow.length - 1; i >= 0 ; i--) {
	    for (var j = 0; j < levelArrow[i].nodes.length; j++) {
	    	// замена текста
	    	if (i === levelArrow.length - 1 && j === 0) {
	    		separator = "";
	    	}
	    	else {
	    	   separator = "\n;\n//////////////////////////////////////////////////////////////////////////////////////////\n";
	    	}
	    	if (nodeToReplace === levelArrow[i].nodes[j]) { 
	    	    totalText = totalText + separator + textToReplace;
	    	}
	    	else {
	    	    totalText = totalText + separator + levelArrow[i].nodes[j].text;
	    	}
	    	
	    	// вставка текста уничтожения таблиц
	    	if (i === 0 && j === levelArrow[i].nodes.length - 1) {
	    		break;
	    	}
	    	nodeWhithAllChildrens = getNodesExtendedWithAllChildrens([levelArrow[i].nodes[j]]);
	    	for (var q = 0; q < nodeWhithAllChildrens.length; q++) {
	    		restNodes.splice(restNodes.indexOf(nodeWhithAllChildrens[q]), 1);
	    	}
	    	for (var k = 0; k < tablesToInsertDropText.length;) {
	    	    var isUseless = true;
	    	    for (var l = 0; l < restNodes.length; l++) {
	    	    	if (restNodes[l].own_in_tables.indexOf(tablesToInsertDropText[k].toUpperCase()) >= 0) {
                    	isUseless = false;
                    }
	    	    	if (restNodes[l].name === tablesToInsertDropText[k]) {
                    	isUseless = false;
                    }
                }
                if (isUseless) {
                    totalText = totalText + "\n;\n//////////////////////////////////////////////////////////////////////////////////////////\nУНИЧТОЖИТЬ\n\t" + tablesToInsertDropText[k];
                    tablesToInsertDropText.splice(k, 1);
				}
				else {
				    k++;
				}
	    	}
	    }
	}
	return totalText;
}

