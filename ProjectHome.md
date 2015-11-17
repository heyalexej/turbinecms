TurbineCMS is a lightweight CMS designed to run on Google App Engine. You can add new pages and subpages, can upload and manage images and you can edit the site template. That's it.

[See it in action](http://www.turbinecms.com)

### NB!!! ###

The original author discontinued this project. If you are still interested in TurbineCMS, check out https://github.com/BauweBijl/TurbineCMS which is the most active fork of TurbineCMS

### Installation instructions ###

1. Download the source from the sidebar

> - or checkout the code with the following command:

`svn checkout http://turbinecms.googlecode.com/svn/trunk/ turbinecms-read-only`

2. Edit _app.yaml_ and set the correct appication ID

3. Deploy the code to Google App Engine

4. Visit http://your_app_ID.appspot.com/admin to get started (application admins only!)

5. If an error message appears about indexes, then wait a moment (server hasn't build yet all needed database indexes)