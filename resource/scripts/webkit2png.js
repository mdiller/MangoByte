var system = require('system');
var page = require('webpage').create();

page.onError = function(msg, trace) {
	var msgStack = ['PHANTOM ERROR: ' + msg];
	if (trace && trace.length) {
		msgStack.push('TRACE:');
		trace.forEach(function(t) {
			msgStack.push(' -> ' + (t.file || t.sourceURL) + ': ' + t.line + (t.function ? ' (in function ' + t.function +')' : ''));
		});
	}
	console.error(msgStack.join('\n'));
	phantom.exit(1);
};

if (system.args.length != 3){
	console.log('usage: phantomjs webkit2img.js <webpage> <filename>');
}

page.viewportSize = { width: 1920, height: 1080 };
page.open(system.args[1], function() {
	var clipRect = page.evaluate(function(){
		return document.querySelector('body').getBoundingClientRect();
	});

	page.clipRect = {
		top:    clipRect.top,
		left:   clipRect.left,
		width:  clipRect.width,
		height: clipRect.height
	};
	window.setTimeout(function () {
		page.render(system.args[2]);
		phantom.exit();
	}, 2000); // Change timeout as required to allow sufficient time 
});
