#! /usr/bin/env python3
#
# Author: Gaute Hope <eg@gaute.vetsj.com> / 2017-03-05
#

import  os, sys
import  argparse
from    oauth2client import tools
import  googleapiclient
import  notmuch

from .remote import *
from .local  import *

class Gmailieer:
  cwd = None

  def main (self):
    parser = argparse.ArgumentParser ('gmi', parents = [tools.argparser])
    self.parser = parser

    common = argparse.ArgumentParser (add_help = False)
    common.add_argument ('-C', '--path', type = str, default = None, help = 'path')

    common.add_argument ('-c', '--credentials', type = str, default = None,
        help = 'optional credentials file for google api')

    common.add_argument ('-s', '--no-progress', action = 'store_true',
        default = False, help = 'Disable progressbar (always off when output is not TTY)')

    subparsers = parser.add_subparsers (help = 'actions', dest = 'action')
    subparsers.required = True

    # pull
    parser_pull = subparsers.add_parser ('pull',
        help = 'pull new e-mail and remote tag-changes',
        description = 'pull',
        parents = [common]
        )

    parser_pull.add_argument ('-t', '--list-labels', action='store_true', default = False,
        help = 'list all remote labels (pull)')

    parser_pull.add_argument ('--limit', type = int, default = None,
        help = 'Maximum number of messages to pull (soft limit, GMail may return more), note that this may upset the tally of synchronized messages.')


    parser_pull.add_argument ('-d', '--dry-run', action='store_true',
        default = False, help = 'do not make any changes')

    parser_pull.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Force a full synchronization to be performed')

    parser_pull.add_argument ('-r', '--remove', action = 'store_true',
        default = False, help = 'Remove files locally when they have been deleted remotely (forces full sync)')

    parser_pull.set_defaults (func = self.pull)

    # push
    parser_push = subparsers.add_parser ('push', parents = [common],
        description = 'push',
        help = 'push local tag-changes')

    parser_push.add_argument ('--limit', type = int, default = None,
        help = 'Maximum number of messages to push, note that this may upset the tally of synchronized messages.')

    parser_push.add_argument ('-d', '--dry-run', action='store_true',
        default = False, help = 'do not make any changes')

    parser_push.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Push even when there has been remote changes (might overwrite remote tag-changes)')

    parser_push.set_defaults (func = self.push)

    # send
    parser_send = subparsers.add_parser ('send', parents = [common],
        description = 'send',
        help = 'send message')

    parser_send.add_argument ('-d', '--dry-run', action='store_true',
        default = False, help = 'do not actually send message')

    # ignored arguments for sendmail compatability
    parser_send.add_argument('-t', type = str, help = 'Ignored: always implied, allowed for sendmail compatability.', dest = 'i0')

    parser_send.add_argument('-f', type = str, help = 'Ignored: has no effect, allowed for sendmail compatability.', dest = 'i1')

    parser_send.add_argument('-o', type = str, help = 'Ignored: has no effect, allowed for sendmail compatability.', dest = 'i2')

    parser_send.add_argument('-i', action='store_true', default = None, help = 'Ignored: always implied, allowed for sendmail compatability.', dest = 'i3')

    parser_send.add_argument('message', nargs = '?', default = '-',
        help = 'MIME message to send (or stdin "-", default)')

    parser_send.set_defaults (func = self.send)

    # sync
    parser_sync = subparsers.add_parser ('sync', parents = [common],
        description = 'sync',
        help = 'sync changes (flags have same meaning as for push and pull)')

    parser_sync.add_argument ('--limit', type = int, default = None,
        help = 'Maximum number of messages to sync, note that this may upset the tally of synchronized messages.')

    parser_sync.add_argument ('-d', '--dry-run', action='store_true',
        default = False, help = 'do not make any changes')

    parser_sync.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Push even when there has been remote changes, and force a full remote-to-local synchronization')

    parser_sync.add_argument ('-r', '--remove', action = 'store_true',
        default = False, help = 'Remove files locally when they have been deleted remotely (forces full sync)')

    parser_sync.set_defaults (func = self.sync)

    # auth
    parser_auth = subparsers.add_parser ('auth', parents = [common],
        description = 'authorize',
        help = 'authorize lieer with your GMail account')

    parser_auth.add_argument ('-f', '--force', action = 'store_true',
        default = False, help = 'Re-authorize')

    parser_auth.set_defaults (func = self.authorize)

    # init
    parser_init = subparsers.add_parser ('init', parents = [common],
        description = 'initialize',
        help = 'initialize local e-mail repository and authorize')

    parser_init.add_argument ('--replace-slash-with-dot', action = 'store_true', default = False,
        help = 'This will replace \'/\' with \'.\' in gmail labels (make sure you realize the implications)')

    parser_init.add_argument ('--no-auth', action = 'store_true', default = False,
        help = 'Do not immediately authorize as well (you will need to run \'auth\' afterwards)')

    parser_init.add_argument ('account', type = str, help = 'GMail account to use')

    parser_init.set_defaults (func = self.initialize)


    # set option
    parser_set = subparsers.add_parser ('set',
        description = 'set option',
        parents = [common],
        help = 'set options for repository')

    parser_set.add_argument ('-t', '--timeout', type = float,
        default = None, help = 'Set HTTP timeout in seconds (0 means forever or system timeout)')

    parser_set.add_argument ('--replace-slash-with-dot', action = 'store_true', default = False,
        help = 'This will replace \'/\' with \'.\' in gmail labels (Important: see the manual and make sure you realize the implications)')

    parser_set.add_argument ('--no-replace-slash-with-dot', action = 'store_true', default = False)

    parser_set.add_argument ('--drop-non-existing-labels', action = 'store_true', default = False,
        help = 'Allow missing labels on the GMail side to be dropped (see https://github.com/gauteh/lieer/issues/48)')

    parser_set.add_argument ('--no-drop-non-existing-labels', action = 'store_true', default = False)

    parser_set.add_argument ('--ignore-empty-history', action = 'store_true', default = False,
        help = 'Sometimes GMail indicates more changes, but an empty set is returned (see https://github.com/gauteh/lieer/issues/120)')

    parser_set.add_argument ('--no-ignore-empty-history', action = 'store_true', default = False)

    parser_set.add_argument ('--ignore-tags-local', type = str,
        default = None, help = 'Set custom tags to ignore when syncing from local to remote (comma-separated, after translations). Important: see the manual.')

    parser_set.add_argument ('--ignore-tags-remote', type = str,
        default = None, help = 'Set custom tags to ignore when syncing from remote to local (comma-separated, before translations). Important: see the manual.')

    parser_set.add_argument ('--file-extension', type = str, default = None,
        help = 'Add a file extension before the maildir status flags (e.g.: "mbox"). Important: see the manual about changing this setting after initial sync.')

    parser_set.set_defaults (func = self.set)


    args        = parser.parse_args (sys.argv[1:])
    self.args   = args

    args.func (args)

  def initialize (self, args):
    self.setup (args, False)
    self.local.initialize_repository (args.replace_slash_with_dot, args.account)

    if not args.no_auth:
      self.local.load_repository ()
      self.remote = Remote (self)

      try:
        self.remote.authorize ()
      except:
        print ("")
        print ("")
        print ("init: repository is set up, but authorization failed. re-run 'gmi auth' with proper parameters to complete authorization")
        print ("")
        print ("")
        print ("")
        print ("")
        raise

  def authorize (self, args):
    print ("authorizing..")
    self.setup (args, False, True)
    self.remote.authorize (args.force)

  def setup (self, args, dry_run = False, load = False, block = False):
    global tqdm

    # common options
    if args.path is not None:
      print("path: %s" % args.path)
      if args.action == "init" and not os.path.exists(args.path):
        os.makedirs(args.path)

      if os.path.isdir(args.path):
        self.cwd = os.getcwd()
        os.chdir(args.path)
      else:
        print("error: %s is not a valid path!" % args.path)
        raise NotADirectoryError("error: %s is not a valid path!" % args.path)

    self.dry_run          = dry_run
    self.HAS_TQDM         = (not args.no_progress)
    self.credentials_file = args.credentials

    if self.HAS_TQDM:
      if not (sys.stderr.isatty() and sys.stdout.isatty()):
        self.HAS_TQDM = False
      else:
        try:
          from tqdm import tqdm
          self.HAS_TQDM = True
        except ImportError:
          self.HAS_TQDM = False

    if not self.HAS_TQDM:
      from .nobar import tqdm

    if self.dry_run:
      print ("dry-run: ", self.dry_run)

    self.local  = Local (self)
    if load:
      self.local.load_repository (block)
      self.remote = Remote (self)

  def sync (self, args):
    self.setup (args, args.dry_run, True)
    self.force            = args.force
    self.limit            = args.limit
    self.list_labels      = False

    self.remote.get_labels ()

    # will try to push local changes, this operation should not make
    # any changes to the local store or any of the file names.
    self.push (args, True)

    # will pull in remote changes, overwriting local changes and effectively
    # resolving any conflicts.
    self.pull (args, True)

  def push (self, args, setup = False):
    if not setup:
      self.setup (args, args.dry_run, True)

      self.force            = args.force
      self.limit            = args.limit

      self.remote.get_labels ()

    # loading local changes
    with notmuch.Database () as db:
      (rev, uuid) = db.get_revision ()

      if rev == self.local.state.lastmod:
        print ("push: everything is up-to-date.")
        return

      qry = "path:%s/** and lastmod:%d..%d" % (self.local.nm_relative, self.local.state.lastmod, rev)

      # print ("collecting changes..: %s" % qry)
      query = notmuch.Query (db, qry)
      total = query.count_messages () # probably destructive here as well
      query = notmuch.Query (db, qry)

      messages = list(query.search_messages ())
      if self.limit is not None and len(messages) > self.limit:
        messages = messages[:self.limit]

      # get gids and filter out messages outside this repository
      messages, gids = self.local.messages_to_gids (messages)

      # get meta-data on changed messages from remote
      remote_messages = []
      bar = tqdm (leave = True, total = len(gids), desc = 'receiving metadata')

      def _got_msgs (ms):
        for m in ms:
          bar.update (1)
          remote_messages.append (m)

      self.remote.get_messages (gids, _got_msgs, 'minimal')
      bar.close ()

      # resolve changes
      bar = tqdm (leave = True, total = len(gids), desc = 'resolving changes')
      actions = []
      for rm, nm in zip(remote_messages, messages):
        actions.append (self.remote.update (rm, nm, self.local.state.last_historyId, self.force))
        bar.update (1)

      bar.close ()

      # remove no-ops
      actions = [ a for a in actions if a ]

      # limit
      if self.limit is not None and len(actions) >= self.limit:
        actions = actions[:self.limit]

      # push changes
      if len(actions) > 0:
        bar = tqdm (leave = True, total = len(actions), desc = 'pushing, 0 changed')
        changed = 0

        def cb (resp):
          nonlocal changed
          bar.update (1)
          changed += 1
          bar.set_description ('pushing, %d changed' % changed)

        self.remote.push_changes (actions, cb)

        bar.close ()
      else:
        print ('push: nothing to push')

    if not self.remote.all_updated:
      # will not set last_mod, this forces messages to be pushed again at next push
      print ("push: not all changes could be pushed, will re-try at next push.")
    else:
      # TODO: Once we get more confident we might set the last history Id here to
      # avoid pulling back in the changes we just pushed. Currently there's a race
      # if something is modified remotely (new email, changed tags), so this might
      # not really be possible.
      pass

    if not self.dry_run and self.remote.all_updated:
      self.local.state.set_lastmod (rev)

    print ("remote historyId: %d" % self.remote.get_current_history_id (self.local.state.last_historyId))

  def pull (self, args, setup = False):
    if not setup:
      self.setup (args, args.dry_run, True)

      self.list_labels      = args.list_labels
      self.force            = args.force
      self.limit            = args.limit

      self.remote.get_labels () # to make sure label map is initialized

    self.remove           = args.remove

    if self.list_labels:
      if self.remove or self.force or self.limit:
        raise argparse.ArgumentError ("-t cannot be specified together with -f, -r or --limit")
      for k,l in self.remote.labels.items ():
        print ("{0: <30} {1}".format (l, k))
      return

    if self.force:
      print ("pull: full synchronization (forced)")
      self.full_pull ()

    elif self.local.state.last_historyId == 0:
      print ("pull: full synchronization (no previous synchronization state)")
      self.full_pull ()

    elif self.remove:
      print ("pull: full synchronization (removing deleted messages)")
      self.full_pull ()

    else:
      print ("pull: partial synchronization.. (hid: %d)" % self.local.state.last_historyId)
      self.partial_pull ()

  def partial_pull (self):
    # get history
    bar         = None
    history     = []
    last_id     = self.remote.get_current_history_id (self.local.state.last_historyId)

    try:
      for hist in self.remote.get_history_since (self.local.state.last_historyId):
        history.extend (hist)

        if bar is None:
          bar = tqdm (leave = True, desc = 'fetching changes')

        bar.update (len(hist))

        if self.limit is not None and len(history) >= self.limit:
          break

    except googleapiclient.errors.HttpError as excep:
      if excep.resp.status == 404:
        print ("pull: historyId is too old, full sync required.")
        self.full_pull ()
        return
      else:
        raise

    except Remote.NoHistoryException as excep:
      print ("pull: failed, re-try in a bit.")
      raise

    finally:
      if bar is not None: bar.close ()

    # figure out which changes need to be applied
    added_messages   = [] # added messages, if they are later deleted they will be
                          # removed from this list

    deleted_messages = [] # deleted messages, if they are later added they will be
                          # removed from this list

    labels_changed   = [] # list of messages which have had their label changed
                          # the entry will be the last and most recent one in case
                          # of multiple changes. if the message is either deleted
                          # or added after the label change it will be removed from
                          # this list.

    def remove_from_all (m):
      nonlocal added_messages, deleted_messages, labels_changed
      remove_from_list (deleted_messages, m)
      remove_from_list (labels_changed, m)
      remove_from_list (added_messages, m)

    def remove_from_list (lst, m):
      e = next ((e for e in lst if e['id'] ==  m['id']), None)
      if e is not None:
        lst.remove (e)
        return True
      return False

    if len(history) > 0:
      bar = tqdm (total = len(history), leave = True, desc = 'resolving changes')
    else:
      bar = None

    for h in history:
      if 'messagesAdded' in h:
        for m in h['messagesAdded']:
          mm = m['message']
          if not (set(mm.get('labelIds', [])) & self.remote.not_sync):
            remove_from_all (mm)
            added_messages.append (mm)

      if 'messagesDeleted' in h:
        for m in h['messagesDeleted']:
          mm = m['message']
          # might silently fail to delete this
          remove_from_all (mm)
          if self.local.has (mm['id']):
            deleted_messages.append (mm)

      # messages that are subsequently deleted by a later action will be removed
      # from either labels_changed or added_messages.
      if 'labelsAdded' in h:
        for m in h['labelsAdded']:
          mm = m['message']
          if not (set(mm.get('labelIds', [])) & self.remote.not_sync):
            new = remove_from_list (added_messages, mm) or not self.local.has (mm['id'])
            remove_from_list (labels_changed, mm)
            if new:
              added_messages.append (mm) # needs to fetched
            else:
              labels_changed.append (mm)
          else:
            # in case a not_sync tag has been added to a scheduled message
            remove_from_list (added_messages, mm)
            remove_from_list (labels_changed, mm)

            if self.local.has (mm['id']):
              remove_from_list (deleted_messages, mm)
              deleted_messages.append (mm)

      if 'labelsRemoved' in h:
        for m in h['labelsRemoved']:
          mm = m['message']
          if not (set(mm.get('labelIds', [])) & self.remote.not_sync):
            new = remove_from_list (added_messages, mm) or not self.local.has (mm['id'])
            remove_from_list (labels_changed, mm)
            if new:
              added_messages.append (mm) # needs to fetched
            else:
              labels_changed.append (mm)
          else:
            # in case a not_sync tag has been added
            remove_from_list (added_messages, mm)
            remove_from_list (labels_changed, mm)

            if self.local.has (mm['id']):
              remove_from_list (deleted_messages, mm)
              deleted_messages.append (mm)

      bar.update (1)

    if bar: bar.close ()

    changed = False
    # fetching new messages
    if len (added_messages) > 0:
      message_gids = [m['id'] for m in added_messages]
      updated     = self.get_content (message_gids)

      # updated labels for the messages that already existed
      needs_update_gid = list(set(message_gids) - set(updated))
      needs_update = [m for m in added_messages if m['id'] in needs_update_gid]
      labels_changed.extend (needs_update)

      changed = True

    if len (deleted_messages) > 0:
      with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
        for m in tqdm (deleted_messages, leave = True, desc = 'removing messages'):
          self.local.remove (m['id'], db)

      changed = True

    if len (labels_changed) > 0:
      lchanged = 0
      with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
        bar = tqdm (total = len(labels_changed), leave = True, desc = 'updating tags (0)')
        for m in labels_changed:
          r = self.local.update_tags (m, None, db)
          if r:
            lchanged += 1
            bar.set_description ('updating tags (%d)' % lchanged)

          bar.update (1)
        bar.close ()


      changed = True

    if not changed:
      print ("pull: everything is up-to-date.")

    if not self.dry_run:
      self.local.state.set_last_history_id (last_id)

    if (last_id > 0):
      print ('current historyId: %d' % last_id)

  def full_pull (self):
    total = 1

    bar = tqdm (leave = True, total = total, desc = 'fetching messages')

    # NOTE:
    # this list might grow gigantic for large quantities of e-mail, not really sure
    # about how much memory this will take. this is just a list of some
    # simple metadata like message ids.
    message_gids = []
    last_id      = self.remote.get_current_history_id (self.local.state.last_historyId)

    for mset in self.remote.all_messages ():
      (total, gids) = mset

      bar.total = total
      bar.update (len(gids))

      for m in gids:
        message_gids.append (m['id'])

      if self.limit is not None and len(message_gids) >= self.limit:
        break

    bar.close ()

    if self.remove:
      if self.limit and not self.dry_run:
        raise argparse.ArgumentError ('--limit with --remove will cause lots of messages to be deleted')

      # removing files that have been deleted remotely
      all_remote = set (message_gids)
      all_local  = set (self.local.gids.keys ())
      remove     = list(all_local - all_remote)
      bar = tqdm (leave = True, total = len(remove), desc = 'removing deleted')
      with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
        for m in remove:
          self.local.remove (m, db)
          bar.update (1)

      bar.close ()

    if len(message_gids) > 0:
      # get content for new messages
      updated = self.get_content (message_gids)

      # get updated labels for the rest
      needs_update = list(set(message_gids) - set(updated))
      self.get_meta (needs_update)
    else:
      print ("pull: no messages.")

    # set notmuch lastmod time, since we have now synced everything from remote
    # to local
    with notmuch.Database () as db:
      (rev, uuid) = db.get_revision ()

    if not self.dry_run:
      self.local.state.set_lastmod (rev)
      self.local.state.set_last_history_id (last_id)

    print ('current historyId: %d, current revision: %d' % (last_id, rev))

  def get_meta (self, msgids):
    """
    Only gets the minimal message objects in order to check if labels are up-to-date.
    """

    if len (msgids) > 0:

      bar = tqdm (leave = True, total = len(msgids), desc = 'receiving metadata')

      # opening db for whole metadata sync
      def _got_msgs (ms):
        with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
          for m in ms:
            bar.update (1)
            self.local.update_tags (m, None, db)

      self.remote.get_messages (msgids, _got_msgs, 'minimal')

      bar.close ()

    else:
      print ("receiving metadata: everything up-to-date.")


  def get_content (self, msgids):
    """
    Get the full email source of the messages that we do not already have

    Returns:
      list of messages which were updated, these have also been updated in Notmuch and
      does not need to be partially upated.

    """

    need_content = [ m for m in msgids if not self.local.has (m) ]

    if len (need_content) > 0:

      bar = tqdm (leave = True, total = len(need_content), desc = 'receiving content')

      def _got_msgs (ms):
        # opening db per message batch since it takes some time to download each one
        with notmuch.Database (mode = notmuch.Database.MODE.READ_WRITE) as db:
          for m in ms:
            bar.update (1)
            self.local.store (m, db)

      self.remote.get_messages (need_content, _got_msgs, 'raw')

      bar.close ()

    else:
      print ("receiving content: everything up-to-date.")

    return need_content

  def send (self, args):
    self.setup (args, args.dry_run, True, True)
    self.remote.get_labels ()

    if args.message == '-':
      msg = sys.stdin.buffer.read()
      fn = 'stdin'
    else:
      if os.path.isabs(args.message):
        fn = args.message
      else:
        fn = os.path.join(self.cwd, args.message)
      msg = open(fn, 'rb').read()

    # check if in-reply-to is set and find threadId
    threadId = None

    import email
    eml = email.message_from_bytes(msg)
    print ("sending message (%s), from: %s.." % (fn, eml.get('From')))

    if 'In-Reply-To' in eml:
      repl = eml['In-Reply-To'].strip().strip('<>')
      print("looking for original message: %s" % repl)
      with notmuch.Database (mode = notmuch.Database.MODE.READ_ONLY) as db:
        nmsg = db.find_message(repl)
        if nmsg is not None:
          (_, gids) = self.local.messages_to_gids([nmsg])
          if nmsg.get_header('Subject') != eml['Subject']:
            print("warning: subject does not match, might not be able to associate with existing thread.")

          if len(gids) > 0:
            gmsg = self.remote.get_message(gids[0])
            threadId = gmsg['threadId']
            print("found existing thread for new message: %s" % threadId)
          else:
            print("warning: could not find gid of parent message, sent message will not be associated in the same thread")
        else:
          print("warning: could not find parent message, sent message will not be associated in the same thread")

    if not args.dry_run:
      msg = self.remote.send(msg, threadId)
      self.get_content([msg['id']])
      self.get_meta([msg['id']])

    print("message sent successfully: %s" % msg['id'])

  def set (self, args):
    args.credentials = '' # for setup()
    self.setup (args, False, True)

    if args.timeout is not None:
      self.local.config.set_timeout (args.timeout)

    if args.replace_slash_with_dot:
      self.local.config.set_replace_slash_with_dot (args.replace_slash_with_dot)

    if args.no_replace_slash_with_dot:
      self.local.config.set_replace_slash_with_dot (not args.no_replace_slash_with_dot)

    if args.drop_non_existing_labels:
      self.local.config.set_drop_non_existing_label (args.drop_non_existing_labels)

    if args.no_drop_non_existing_labels:
      self.local.config.set_drop_non_existing_label (not args.no_drop_non_existing_labels)

    if args.ignore_empty_history:
      self.local.config.set_ignore_empty_history (True)

    if args.no_ignore_empty_history:
      self.local.config.set_ignore_empty_history (False)

    if args.ignore_tags_local is not None:
      self.local.config.set_ignore_tags (args.ignore_tags_local)

    if args.ignore_tags_remote is not None:
      self.local.config.set_ignore_remote_labels (args.ignore_tags_remote)

    if args.file_extension is not None:
      self.local.config.set_file_extension (args.file_extension)

    print ("Repository information and settings:")
    print ("Account ...........: %s" % self.local.config.account)
    print ("historyId .........: %d" % self.local.state.last_historyId)
    print ("lastmod ...........: %d" % self.local.state.lastmod)
    print ("Timeout ...........: %f" % self.local.config.timeout)
    print ("File extension ....: %s" % self.local.config.file_extension)
    print ("Drop non existing labels...:", self.local.config.drop_non_existing_label)
    print ("Ignore empty history ......:", self.local.config.ignore_empty_history)
    print ("Replace . with / ..........:", self.local.config.replace_slash_with_dot)
    print ("Ignore tags (local) .......:", self.local.config.ignore_tags)
    print ("Ignore labels (remote) ....:", self.local.config.ignore_remote_labels)



