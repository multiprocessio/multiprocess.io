{% extends "blog/layout.tmpl" %}

{% block postTitle %}HTML event handler attributes: down the rabbit hole{% endblock %}
{% block postDate %}April 26, 2022{% endblock %}
{% block postAuthor %}Phil Eaton{% endblock %}
{% block postAuthorEmail %}phil@multiprocess.io{% endblock %}
{% block postTags %}html,javascript{% endblock %}

{% block postBody %}
I was throwing together a license management app for DataStation and
got to form submissions. DataStation has a complex user interface and
benefits from React. But this license management app I wanted to keep
simple using only server-side templates
([Pongo2](https://github.com/flosch/pongo2), a Go clone of Jinja
templates).

But I wanted all of my Go code to just deal with JSON HTTP bodies
rather than multipart/form-data.

A basic form in the app looks like this:

```html
<form method="post">
  <div class="form-row">
    <label>Email: </label><input type="email" name="email"/>
  </div>
  <div class="form-row">
    <label>Password: </label><input type="password" name="password"/>
  </div>

  <button>Sign In</button>
</form>
```

I knew I'd have a bunch of forms around the app. So I wanted to just
have some reusable JavaScript that would turn form submissions into a
POST request and prevent the default behavior of submitting the form.

The JavaScript would look like this:

```javascript
function submit(e) {
  const form = e.target.closest('form');
  if (form.method === 'get') {
    return; // default behavior is ok
  }
  e.preventDefault();

  const values = {};
  for (const el of form.querySelectorAll('input')) {
    values[el.name] = el.value;
  }

  fetch(location.pathname, {
    method: form.method,
    headers: { 'content-type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(values),
  });
}
```

So this way each form could just call this function in some way and
they'd all submit their data as JSON-encoded HTTP bodies.

In each form all I'd have to do is something like this:

```html
<button onclick="submit">...</button>
```

And I'd be set. But I tried that out and nothing happened. So I
switched to `onclick="submit()"`. And that worked. But where is the
event?

Let's check the internet. MDN docs on the [onclick
attribute](https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/onclick#specifications). Nothing. Google
"onclick html attribute access event". Nothing.

All the examples on Google/StackOverflow/MDN do show a function
call. Some show something like `onclick="submit(this)"`. But `this` in
this context is the form not the event. None of them show anything to
do with an event.

I need to pass the event to `submit` to be able to prevent
default. How do I do this?

### Bringing in the cavalry

At this point I started a [Twitter
thread](https://twitter.com/phil_eaton/status/1518675739075301376)
hoping one of my intelligent followers would illuminate me.

### The debugger

Then I opened up the debugger and set a breakpoint within my submit
function. When I set `onclick="submit()"` it does get into this
function.

I noticed that the caller scope is the HTML attribute. And when I
clicked on that I noticed the `event` variable in local scope.

![Event variable in local scope](/event-variable-in-local-scope.png)

Well that looks like it! I set `onclick="submit(event)"` and it works!
I get the submit event I want.

But what the heck is this variable? As I scoured the internet I
noticed `window.event` which is documented in MDN and is marked as
deprecated. Crap. I hope that's not the variable I'm using. Because if
a variable isn't in scope it will get looked up in the window object.

Now Simon Willison [chimed
in](https://twitter.com/simonw/status/1518681988978290688) and
suggested I check `console.log(event === window.event)`. It's
true. But that doesn't mean `event` and `window.event` are the same.

Here's a case illustrating how it could be true:

```javascript
window.x = 1;
function dothing () {
  console.log(x === window.x); // true
}
dothing();
```

But here's a counter example of how they're not necessarily the same
variable.

```javascript
window.x = 1;
function dothing (x) {
  console.log(x === window.x); // true
}
dothing(window.x);
```

`x` is a local variable in scope in the `dothing` function. And it
happens to be equal to `window.x`.

So comparing the `event` and `window.event` isn't enough to know if
`event` is a variable in scope in the function or if it's being looked
up in the window object.

And again, I saw `event` in the debugger in the locals section. So
that kind of sounds like it's a local not a variable in the window
object. Especially since no other variables in the window object are
in the locals section.

### The HTML spec

At this point Simon and I both started simple searches against the
[HTML spec](https://html.spec.whatwg.org/print.pdf) (PDF). There were
no examples `event` showing up in `onclick` attribute values. But I
did start seeing examples of other handlers using `event`.

![Examples of event object in event handler attribute values](/html-spec-event.png)

Seeing examples in the spec made me feel more certain that this was
not `window.event` since `window.event` wasn't something I could find
in the spec. And I assumed the spec wouldn't be using examples of
deprecated code.

Finally, [Colin Dellow found the
point](https://twitter.com/cldellow/status/1518695711654752263) in the
spec where `event` is defined. And turns out: it's a local!

![HTML spec showing event definition](/html-spec-event-definition.png)

### Summary

The spec shows that the string passed to a handler is combined like
this:

```javascript
function $name (event) { $body }
```

I'm not sure what `$name` is but `$body` is the string passed to the
handler attribute in HTML. `event` is an argument. This string becomes
a function through the `Function` constructor I'm assuming.

Good to know! Thank you Simon for digging into the problem and also
amplifying the questions. And thank you Colin for finding the location
in the spec where these event handler attributes are described!

And as a footnote: I ended up switching from `<button onclick` to
`<form onsubmit` since it seems like the latter handles more cases.

#### Share

<blockquote class="twitter-tweet"><p lang="en" dir="ltr">I wrote up my little adventure yesterday trying to understand how HTML event attribute values are evaluated.<br><br>Thanks <a href="https://twitter.com/simonw?ref_src=twsrc%5Etfw">@simonw</a> and <a href="https://twitter.com/cldellow?ref_src=twsrc%5Etfw">@cldellow</a> for helping me find the way! 😆<a href="https://t.co/0MRKqpUkgN">https://t.co/0MRKqpUkgN</a> <a href="https://t.co/Pp1BvUVUQP">pic.twitter.com/Pp1BvUVUQP</a></p>&mdash; Phil Eaton (@phil_eaton) <a href="https://twitter.com/phil_eaton/status/1519048613464268804?ref_src=twsrc%5Etfw">April 26, 2022</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>

{% endblock %}
