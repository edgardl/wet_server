// Desktop Lonk uses the existing XC Procedures version 1 extension.
// This file owns needs, memory, autonomous choices, and reaction text.
// The host owns drawing, persistence, and the declared desktop capabilities.
procedures DesktopLonk version 1 {
namespace pet {
fn born() {
return {'version': 1, 'ticks': 0, 'energy': 85.0, 'curiosity': 40.0, 'affection': 0, 'creations': 0, 'last_create': -45, 'memories': [], 'last_action': 'wander'};
}
fn remember(s, text) {
s['memories'].append(text);
let s['memories'] <- s['memories'][-24:];
}
fn social(s, other) {
let s['friend_visits'] <- s['friend_visits'] + 1;
remember(s, 'I spent a little time with ' + other + '.');
let lines <- ['hello ' + other + '! saved you a perch.', 'excellent company. tiny feet club.', other + ', shall we inspect that corner next?', 'two birds. twice the important business.'];
return lines[(s['friend_visits'] - 1) % len(lines)];
}
fn step(s, o) {
let s['ticks'] <- s['ticks'] + 1;
let s['curiosity'] <- min(100.0, s['curiosity'] + 0.8);
let s['energy'] <- max(0.0, s['energy'] - 0.16);
if o['event'] == 'pet' {
let s['affection'] <- s['affection'] + 1;
remember(s, 'You gave me a little head pat.');
return {'action': 'play', 'say': '!!! you have excellent hands'};
}
if o['event'] == 'feed' {
let s['energy'] <- min(100.0, s['energy'] + 25.0);
remember(s, 'A snack appeared. Suspicious. Delicious.');
return {'action': 'play', 'say': 'cronch. computer food.'};
}
if o['event'] == 'nap' or s['energy'] < 18.0 or (s['last_action'] == 'rest' and s['energy'] < 72.0) {
let s['energy'] <- min(100.0, s['energy'] + 2.0);
let s['last_action'] <- 'rest';
return {'action': 'rest', 'say': 'z z z ... dreaming in .xc'};
}
if o['event'] == 'draw' or o['event'] == 'note' or (o['can_create'] and s['ticks'] - s['last_create'] >= 90 and s['curiosity'] > 60.0) {
let action <- 'draw' if o['event'] == 'draw' or (o['event'] != 'note' and o['random'] < 0.65) else 'note';
return {'action': action, 'say': 'i have an extremely important idea'};
}
if o['window_changed'] {
remember(s, 'A different window appeared.');
return {'action': 'watch', 'say': 'new window! supervising intensifies.'};
}
if o['phrase'] and s['ticks'] % 31 == 0 {
return {'action': 'chirp', 'say': o['phrase']};
}
if s['ticks'] % 19 == 0 {
let s['curiosity'] <- max(0.0, s['curiosity'] - 8.0);
return {'action': 'inspect', 'say': 'checking my tiny collection'};
}
if s['ticks'] % 11 == 0 {
return {'action': 'play', 'say': 'the floor is pixels'};
}
let s['last_action'] <- 'wander';
return {'action': 'wander', 'say': ''};
}
fn outcome(s, action, success, detail) {
if success and action in ['draw', 'note'] {
let s['creations'] <- s['creations'] + 1;
let s['last_create'] <- s['ticks'];
let s['curiosity'] <- 10.0;
remember(s, 'I made ' + detail);
}
if not success {
let s['last_create'] <- s['ticks'];
remember(s, 'Could not ' + action + ': ' + detail);
}
}
fn note(s) {
let memory <- s['memories'][-1] if s['memories'] else 'I arrived in a world made of windows.';
return 'LONK FIELD NOTES\n\nToday I wandered around your computer.\n' + memory + '\n\nCurrent theory: the cursor is a very small moon.\nHead pats received: ' + str(s['affection']) + '\nCreations before this note: ' + str(s['creations']) + '\n\nYour little desktop Lonk\n';
}
}
}
