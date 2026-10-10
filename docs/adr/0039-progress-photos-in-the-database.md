# ADR-0039: Progress photos are kept in the database, cleaned of their metadata

- Status: Accepted
- Date: 2026-10-10
- Deciders: Liam (D3, #143)

## Context

D3 decided progress photos are stored on the Pi, readable only by the app's user and group,
never in logs, share views or public endpoints, and included in the nightly backup and the
desktop pull (which copy the database only). #143 left open where location data is removed:
on the server (with an image library, a new dependency) or in the browser.

## Decision

- **In the database.** Each photo is a row in `progress_photos` (per person, ADR-0029): day,
  pose (front, side, back), the JPEG and its size. One per pose per day; a new upload replaces
  it. That meets D3: the database file is on the Pi with the app's permissions (ADR-0024), and
  the nightly backup, its integrity check, the desktop pull and the restore drill include
  photos with no change. The picture column is loaded only when a photo is asked for.
- **Cleaned on the server, without a library.** Only JPEG is accepted. `domain.photos` walks
  the JPEG's segments and drops every metadata one (EXIF with GPS and time, XMP, other APPn,
  comments), keeping JFIF, the Adobe colour marker and the image data. It walks through each
  scan's image data too, so metadata between the scans of a progressive JPEG is dropped, and
  stops at the first end-of-image marker, dropping anything after it (camera trailers, a second
  picture). A file that isn't a well-formed JPEG is refused. The browser also shrinks photos (longest side 1600 px) and
  re-encodes them, which drops metadata too, but the server doesn't rely on it.
- **Sizes.** Up to 3 MB an upload, read from the request and cut off past the limit. At
  roughly 300 KB a photo and three a retest, that is a few MB a year.
- **Upload is the JPEG as the request body** (`PUT /api/photos/{day}/{pose}`), so no form
  parser is needed. Pictures are served owner-only with `Cache-Control: private, no-store`.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Rows in the database (chosen) | Backups, permissions and restore cover them as they are | The database grows by a few MB a year |
| Files next to the database | Smaller database | Backup, desktop pull and restore drill each need changing, and files and rows can drift |
| Pillow to strip metadata and resize | Handles any format | A large native dependency for a few photos a month |
| Strip only in the browser | No server code | Trusts the client |

## Consequences

- Moving to another server moves photos with the database (D3 is revisited then anyway).
- HEIC and PNG aren't accepted; phones' camera apps give JPEG, and the browser re-encodes
  whatever it can read into JPEG before upload.
