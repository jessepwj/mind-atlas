# Security and privacy policy

mind-atlas builds static HTML pages from text that an AI agent or a person writes, and it asks agents to read
a project's files in order to map them. Both sides have security and privacy consequences, so this page says
what the project promises and how to report a problem.

## Reporting a vulnerability

If you find a security or privacy problem (for example, a way for text in an outline to run script in the
page, or a skill instruction that could make an agent read or leak something it should not), please **do not
open a public issue**. Instead:

- use GitHub's private vulnerability reporting: the **Security** tab of this repository, then
  **Report a vulnerability**; or
- contact the maintainer through the options on their GitHub profile.

You will get an acknowledgement as soon as possible. Please allow reasonable time for a fix before any
public disclosure.

## What the generated page guarantees

- **No network.** The page is one file with a content security policy (`default-src 'none'`), so it cannot
  load anything or send anything anywhere, even if a bug let untrusted text through.
- **Escaped content.** Outline text is embedded as JSON, with `<` escaped, and is written into the page only
  as text. Placeholders and markup in an outline are not interpreted.
- **Local storage only.** Feedback written in the page stays in the browser's `localStorage` until the user
  copies it. Nothing is uploaded.
- **Paths.** By default the page contains the absolute path of the page file and of the reply command, so
  that an AI that receives the copied feedback can answer. These paths can reveal your user name and
  folder layout. Build with `--no-paths` before you share a page or publish it.

## What the skill asks of the agent

The skill tells an agent that follows it to:

- keep research sub-agents **read-only** and cap them at 10 at a time;
- **never put secrets on the map**: no passwords, tokens, keys or private message text, only where they are
  kept and with what permissions;
- delete any temporary file that a sub-agent filled with a secret, and tell the user;
- leave no long-running server behind.

## What the scripts do

`build.py` and `reply.py` only read and write inside the work folder you give them (and read the skill's own
template and string table). They make no network requests and run no other programs, except that `reply.py`
starts `build.py` with the same Python interpreter. They use the standard library only.
