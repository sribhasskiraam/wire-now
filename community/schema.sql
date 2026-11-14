-- =====================================================================
-- Wire Now Community: database for Supabase (Postgres).
-- Safe to run again: it only creates what is missing and refreshes rules.
-- =====================================================================

-- ---------------------------------------------------------------- tables
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  username    text unique not null check (username ~ '^[A-Za-z0-9_]{3,20}$'),
  created_at  timestamptz not null default now(),
  is_admin    boolean not null default false,
  banned      boolean not null default false
);

create table if not exists public.communities (
  id           uuid primary key default gen_random_uuid(),
  slug         text unique not null check (slug ~ '^[a-z0-9_]{3,24}$'),
  name         text not null check (char_length(name) between 3 and 40),
  description  text not null default '' check (char_length(description) <= 300),
  is_official  boolean not null default false,
  created_by   uuid references public.profiles(id) on delete set null default auth.uid(),
  created_at   timestamptz not null default now()
);

create table if not exists public.posts (
  id             uuid primary key default gen_random_uuid(),
  community_id   uuid not null references public.communities(id) on delete cascade,
  author_id      uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  title          text not null check (char_length(title) between 5 and 200),
  body           text not null default '' check (char_length(body) <= 10000),
  url            text check (url is null or url ~ '^https?://[^\s]+$'),
  created_at     timestamptz not null default now(),
  score          integer not null default 0,
  comment_count  integer not null default 0,
  removed        boolean not null default false
);
create index if not exists posts_community_idx on public.posts (community_id, created_at desc);
create index if not exists posts_created_idx on public.posts (created_at desc);

create table if not exists public.comments (
  id          uuid primary key default gen_random_uuid(),
  post_id     uuid not null references public.posts(id) on delete cascade,
  parent_id   uuid references public.comments(id) on delete cascade,
  author_id   uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  body        text not null check (char_length(body) between 1 and 5000),
  created_at  timestamptz not null default now(),
  score       integer not null default 0,
  removed     boolean not null default false
);
create index if not exists comments_post_idx on public.comments (post_id, created_at);

create table if not exists public.post_votes (
  user_id  uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  post_id  uuid not null references public.posts(id) on delete cascade,
  value    smallint not null check (value in (-1, 1)),
  primary key (user_id, post_id)
);

create table if not exists public.comment_votes (
  user_id     uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  comment_id  uuid not null references public.comments(id) on delete cascade,
  value       smallint not null check (value in (-1, 1)),
  primary key (user_id, comment_id)
);

create table if not exists public.reports (
  id          uuid primary key default gen_random_uuid(),
  reporter    uuid references public.profiles(id) on delete set null default auth.uid(),
  post_id     uuid references public.posts(id) on delete cascade,
  comment_id  uuid references public.comments(id) on delete cascade,
  reason      text not null check (char_length(reason) between 3 and 500),
  created_at  timestamptz not null default now(),
  resolved    boolean not null default false,
  check (post_id is not null or comment_id is not null)
);

-- words that are not allowed anywhere (the owner can add more in the Table Editor)
create table if not exists public.banned_words (word text primary key);

-- the owner's email: whoever logs in with it becomes an admin (filled in by the set-up robot)
create table if not exists public.admin_emails (email text primary key);
insert into public.banned_words (word) values ('fuck'), ('cunt'), ('motherfucker'), ('nigger'), ('faggot')
on conflict do nothing;

-- ---------------------------------------------------------------- helpers
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select is_admin from public.profiles where id = auth.uid()), false);
$$;

create or replace function public.check_text(t text) returns void
language plpgsql stable security definer set search_path = public as $$
begin
  if t is null then return; end if;
  if exists (select 1 from public.banned_words w where lower(t) ~ ('\m' || w.word || '\M')) then
    raise exception 'Please keep it respectful: your text contains a word that is not allowed.';
  end if;
end $$;

-- rate limits, bans and the word filter, checked before anything new is saved
create or replace function public.before_new_content() returns trigger
language plpgsql security definer set search_path = public as $$
declare n integer; acct timestamptz;
begin
  if auth.uid() is null then return new; end if;   -- set-up and admin work from the database itself
  if exists (select 1 from public.profiles where id = auth.uid() and banned) then
    raise exception 'Your account has been suspended.';
  end if;
  if tg_table_name = 'posts' then
    perform public.check_text(new.title); perform public.check_text(new.body);
    select count(*) into n from public.posts where author_id = auth.uid() and created_at > now() - interval '1 hour';
    if n >= 5 then raise exception 'You can post up to 5 times an hour. Please try again later.'; end if;
  elsif tg_table_name = 'comments' then
    perform public.check_text(new.body);
    select count(*) into n from public.comments where author_id = auth.uid() and created_at > now() - interval '1 hour';
    if n >= 30 then raise exception 'You can comment up to 30 times an hour. Please slow down.'; end if;
  elsif tg_table_name = 'communities' then
    perform public.check_text(new.name); perform public.check_text(new.description);
    if not public.is_admin() then
      new.is_official := false;
      select created_at into acct from public.profiles where id = auth.uid();
      if acct is null or acct > now() - interval '1 day' then
        raise exception 'New accounts can create communities after 1 day.';
      end if;
      select count(*) into n from public.communities where created_by = auth.uid();
      if n >= 3 then raise exception 'You can create up to 3 communities.'; end if;
    end if;
  elsif tg_table_name = 'reports' then
    select count(*) into n from public.reports where reporter = auth.uid() and created_at > now() - interval '1 hour';
    if n >= 10 then raise exception 'Too many reports in one hour.'; end if;
  end if;
  return new;
end $$;

drop trigger if exists posts_check on public.posts;
create trigger posts_check before insert on public.posts for each row execute function public.before_new_content();
drop trigger if exists comments_check on public.comments;
create trigger comments_check before insert on public.comments for each row execute function public.before_new_content();
drop trigger if exists communities_check on public.communities;
create trigger communities_check before insert on public.communities for each row execute function public.before_new_content();
drop trigger if exists reports_check on public.reports;
create trigger reports_check before insert on public.reports for each row execute function public.before_new_content();

-- usernames are checked by the word filter too
create or replace function public.profile_check() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  perform public.check_text(new.username);
  if tg_op = 'INSERT' then
    new.is_admin := exists (select 1 from auth.users u join public.admin_emails a on lower(a.email) = lower(u.email) where u.id = new.id);
    new.banned := false;
  end if;
  return new;
end $$;
drop trigger if exists profiles_check on public.profiles;
create trigger profiles_check before insert or update of username on public.profiles for each row execute function public.profile_check();

-- keep scores and comment counts up to date
create or replace function public.vote_changed() returns trigger
language plpgsql security definer set search_path = public as $$
declare delta integer;
begin
  delta := coalesce(case when tg_op <> 'DELETE' then new.value end, 0) - coalesce(case when tg_op <> 'INSERT' then old.value end, 0);
  if tg_table_name = 'post_votes' then
    update public.posts set score = score + delta where id = coalesce(new.post_id, old.post_id);
  else
    update public.comments set score = score + delta where id = coalesce(new.comment_id, old.comment_id);
  end if;
  return null;
end $$;
drop trigger if exists post_votes_score on public.post_votes;
create trigger post_votes_score after insert or update or delete on public.post_votes for each row execute function public.vote_changed();
drop trigger if exists comment_votes_score on public.comment_votes;
create trigger comment_votes_score after insert or update or delete on public.comment_votes for each row execute function public.vote_changed();

create or replace function public.comment_counted() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'INSERT' then
    update public.posts set comment_count = comment_count + 1 where id = new.post_id;
  elsif tg_op = 'DELETE' then
    update public.posts set comment_count = greatest(0, comment_count - 1) where id = old.post_id;
  end if;
  return null;
end $$;
drop trigger if exists comments_count on public.comments;
create trigger comments_count after insert or delete on public.comments for each row execute function public.comment_counted();

-- admins remove or restore posts/comments, resolve reports, and ban users
create or replace function public.moderate(kind text, target uuid, remove boolean default true) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can do this.'; end if;
  if kind = 'post' then update public.posts set removed = remove where id = target;
  elsif kind = 'comment' then update public.comments set removed = remove where id = target;
  elsif kind = 'ban' then update public.profiles set banned = remove where id = target;
  elsif kind = 'report' then update public.reports set resolved = remove where id = target;
  else raise exception 'Unknown action'; end if;
end $$;

-- ---------------------------------------------------------------- feed (hot ranking like Reddit)
create or replace view public.feed with (security_invoker = true) as
select p.id, p.title, p.body, p.url, p.created_at, p.score, p.comment_count, p.removed,
       c.slug as community, c.name as community_name, c.is_official,
       pr.username as author, p.author_id,
       (p.score + 1) / power(extract(epoch from (now() - p.created_at)) / 3600 + 2, 1.5) as hot
from public.posts p
join public.communities c on c.id = p.community_id
join public.profiles pr on pr.id = p.author_id
where not p.removed;

create or replace view public.thread with (security_invoker = true) as
select cm.id, cm.post_id, cm.parent_id, cm.body, cm.created_at, cm.score, cm.removed,
       pr.username as author, cm.author_id
from public.comments cm
join public.profiles pr on pr.id = cm.author_id;

-- ---------------------------------------------------------------- who may do what (row level security)
alter table public.profiles      enable row level security;
alter table public.communities   enable row level security;
alter table public.posts         enable row level security;
alter table public.comments      enable row level security;
alter table public.post_votes    enable row level security;
alter table public.comment_votes enable row level security;
alter table public.reports       enable row level security;
alter table public.banned_words  enable row level security;
alter table public.admin_emails  enable row level security;

drop policy if exists "read profiles" on public.profiles;
create policy "read profiles" on public.profiles for select using (true);
drop policy if exists "create own profile" on public.profiles;
create policy "create own profile" on public.profiles for insert to authenticated with check (id = auth.uid());
drop policy if exists "rename own profile" on public.profiles;
create policy "rename own profile" on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists "read communities" on public.communities;
create policy "read communities" on public.communities for select using (true);
drop policy if exists "create community" on public.communities;
create policy "create community" on public.communities for insert to authenticated with check (created_by = auth.uid());
drop policy if exists "admins edit communities" on public.communities;
create policy "admins edit communities" on public.communities for update to authenticated using (public.is_admin());

drop policy if exists "read posts" on public.posts;
create policy "read posts" on public.posts for select using (not removed or author_id = auth.uid() or public.is_admin());
drop policy if exists "create post" on public.posts;
create policy "create post" on public.posts for insert to authenticated with check (author_id = auth.uid() and not removed);
drop policy if exists "delete own post" on public.posts;
create policy "delete own post" on public.posts for delete to authenticated using (author_id = auth.uid());

drop policy if exists "read comments" on public.comments;
create policy "read comments" on public.comments for select using (not removed or author_id = auth.uid() or public.is_admin());
drop policy if exists "create comment" on public.comments;
create policy "create comment" on public.comments for insert to authenticated with check (author_id = auth.uid() and not removed);
drop policy if exists "delete own comment" on public.comments;
create policy "delete own comment" on public.comments for delete to authenticated using (author_id = auth.uid());

drop policy if exists "own post votes" on public.post_votes;
create policy "own post votes" on public.post_votes for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own comment votes" on public.comment_votes;
create policy "own comment votes" on public.comment_votes for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "send report" on public.reports;
create policy "send report" on public.reports for insert to authenticated with check (reporter = auth.uid());
drop policy if exists "admins read reports" on public.reports;
create policy "admins read reports" on public.reports for select to authenticated using (public.is_admin());

drop policy if exists "admins read banned words" on public.banned_words;
create policy "admins read banned words" on public.banned_words for select to authenticated using (public.is_admin());

-- column rights: people can only change what they should
revoke all on public.profiles, public.communities, public.posts, public.comments,
              public.post_votes, public.comment_votes, public.reports, public.banned_words, public.admin_emails from anon, authenticated;
grant select on public.profiles, public.communities, public.posts, public.comments, public.feed, public.thread to anon, authenticated;
grant insert (id, username) on public.profiles to authenticated;
grant update (username) on public.profiles to authenticated;
grant insert (slug, name, description) on public.communities to authenticated;
grant update (name, description, is_official) on public.communities to authenticated;
grant insert (community_id, title, body, url) on public.posts to authenticated;
grant delete on public.posts to authenticated;
grant insert (post_id, parent_id, body) on public.comments to authenticated;
grant delete on public.comments to authenticated;
grant select, insert, update, delete on public.post_votes, public.comment_votes to authenticated;
grant insert (post_id, comment_id, reason) on public.reports to authenticated;
grant select on public.reports, public.banned_words to authenticated;
grant execute on function public.moderate(text, uuid, boolean), public.is_admin() to authenticated;

-- ---------------------------------------------------------------- the official topic communities
insert into public.communities (slug, name, description, is_official, created_by) values
  ('news',      'Wire Now News', 'Discuss the stories from Wire Now.', true, null),
  ('politics',  'Politics',      'Sri Lankan and world politics.', true, null),
  ('economy',   'Economy',       'Prices, the rupee, jobs, the budget and the economy.', true, null),
  ('business',  'Business',      'Companies, startups and work.', true, null),
  ('sports',    'Sports',        'Cricket, rugby, football and all sports.', true, null),
  ('tech',      'Tech',          'Technology, phones, the internet and AI.', true, null),
  ('health',    'Health',        'Health news and wellbeing. Not medical advice.', true, null),
  ('weather',   'Weather & Alerts', 'Weather, floods, landslides and safety alerts.', true, null),
  ('local',     'Local Area',    'News and questions from your town or village.', true, null),
  ('society',   'Society',       'Education, culture, transport and everyday life.', true, null)
on conflict (slug) do nothing;

-- =====================================================================
-- PART 2: a calm social space for introverts and ambiverts
-- profiles, quiet follows, status posts, reposts, blocks, private and
-- group chats, notifications and silent phone pop-ups.
-- =====================================================================

-- ---------------------------------------------------------------- profiles
alter table public.profiles add column if not exists display_name text check (char_length(display_name) <= 40);
alter table public.profiles add column if not exists bio text not null default '' check (char_length(bio) <= 300);
alter table public.profiles add column if not exists dm_policy text not null default 'following' check (dm_policy in ('everyone','following','nobody'));

-- ---------------------------------------------------------------- status posts (posts without a topic) and reposts
alter table public.posts alter column community_id drop not null;
alter table public.posts alter column title set default '';
alter table public.posts drop constraint if exists posts_title_check;
alter table public.posts add constraint posts_title_check check (community_id is null or char_length(title) between 5 and 200);
alter table public.posts drop constraint if exists posts_status_check;
alter table public.posts add constraint posts_status_check check (community_id is not null or (title = '' and url is null and char_length(body) between 1 and 1000));
create index if not exists posts_author_idx on public.posts (author_id, created_at desc);

create table if not exists public.follows (
  follower    uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  followee    uuid not null references public.profiles(id) on delete cascade,
  created_at  timestamptz not null default now(),
  primary key (follower, followee),
  check (follower <> followee)
);
create index if not exists follows_followee_idx on public.follows (followee);

create table if not exists public.blocks (
  blocker     uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  blocked     uuid not null references public.profiles(id) on delete cascade,
  created_at  timestamptz not null default now(),
  primary key (blocker, blocked),
  check (blocker <> blocked)
);

create table if not exists public.reposts (
  user_id     uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  post_id     uuid not null references public.posts(id) on delete cascade,
  created_at  timestamptz not null default now(),
  primary key (user_id, post_id)
);

create or replace function public.is_blocked(a uuid, b uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.blocks where (blocker = a and blocked = b) or (blocker = b and blocked = a));
$$;

-- ---------------------------------------------------------------- chats
create table if not exists public.conversations (
  id               uuid primary key default gen_random_uuid(),
  is_group         boolean not null default false,
  title            text check (char_length(title) <= 60),
  created_by       uuid references public.profiles(id) on delete set null,
  created_at       timestamptz not null default now(),
  last_message_at  timestamptz not null default now()
);

create table if not exists public.conversation_members (
  conversation_id  uuid not null references public.conversations(id) on delete cascade,
  user_id          uuid not null references public.profiles(id) on delete cascade,
  joined_at        timestamptz not null default now(),
  last_read_at     timestamptz not null default now(),
  muted            boolean not null default false,
  primary key (conversation_id, user_id)
);
create index if not exists members_user_idx on public.conversation_members (user_id);

create table if not exists public.messages (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid not null references public.conversations(id) on delete cascade,
  sender_id        uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  body             text not null check (char_length(body) between 1 and 4000),
  created_at       timestamptz not null default now(),
  removed          boolean not null default false
);
create index if not exists messages_conv_idx on public.messages (conversation_id, created_at desc);

alter table public.reports add column if not exists message_id uuid references public.messages(id) on delete cascade;
alter table public.reports drop constraint if exists reports_check;
alter table public.reports add constraint reports_check check (post_id is not null or comment_id is not null or message_id is not null);

create or replace function public.is_member(cid uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.conversation_members where conversation_id = cid and user_id = auth.uid());
$$;

-- may person "me" start a chat with "other"?
create or replace function public.can_message(me uuid, other uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select me <> other
     and not public.is_blocked(me, other)
     and coalesce((select not banned from public.profiles where id = me), false)
     and case (select dm_policy from public.profiles where id = other)
           when 'everyone'  then true
           when 'following' then exists (select 1 from public.follows where follower = other and followee = me)
           else false end;
$$;

-- open (or reuse) a private chat
create or replace function public.start_dm(other uuid) returns uuid
language plpgsql security definer set search_path = public as $$
declare me uuid := auth.uid(); cid uuid;
begin
  if me is null then raise exception 'Please log in.'; end if;
  select c.id into cid from public.conversations c
    join public.conversation_members a on a.conversation_id = c.id and a.user_id = me
    join public.conversation_members b on b.conversation_id = c.id and b.user_id = other
   where not c.is_group limit 1;
  if cid is not null then
    if public.is_blocked(me, other) then raise exception 'You can''t message this person.'; end if;
    return cid;
  end if;
  if not public.can_message(me, other) then
    raise exception 'This person only accepts messages from people they follow.';
  end if;
  insert into public.conversations (is_group, created_by) values (false, me) returning id into cid;
  insert into public.conversation_members (conversation_id, user_id) values (cid, me), (cid, other);
  return cid;
end $$;

-- make a group; people who don't accept messages from you are left out quietly
create or replace function public.create_group(title text, members uuid[]) returns uuid
language plpgsql security definer set search_path = public as $$
declare me uuid := auth.uid(); cid uuid; m uuid; n integer;
begin
  if me is null then raise exception 'Please log in.'; end if;
  if coalesce(char_length(trim(title)), 0) < 2 then raise exception 'Give the group a name.'; end if;
  perform public.check_text(title);
  select count(*) into n from public.conversations where created_by = me and is_group and created_at > now() - interval '1 day';
  if n >= 5 then raise exception 'You can create up to 5 groups a day.'; end if;
  insert into public.conversations (is_group, title, created_by) values (true, trim(title), me) returning id into cid;
  insert into public.conversation_members (conversation_id, user_id) values (cid, me);
  foreach m in array coalesce(members, '{}') loop
    exit when (select count(*) from public.conversation_members where conversation_id = cid) >= 50;
    if public.can_message(me, m) then
      insert into public.conversation_members (conversation_id, user_id) values (cid, m) on conflict do nothing;
    end if;
  end loop;
  return cid;
end $$;

create or replace function public.add_to_group(cid uuid, who uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from public.conversations where id = cid and is_group and created_by = auth.uid()) then
    raise exception 'Only the group creator can add people.';
  end if;
  if (select count(*) from public.conversation_members where conversation_id = cid) >= 50 then raise exception 'Groups can have up to 50 people.'; end if;
  if not public.can_message(auth.uid(), who) then raise exception 'This person doesn''t accept messages from you.'; end if;
  insert into public.conversation_members (conversation_id, user_id) values (cid, who) on conflict do nothing;
end $$;

create or replace function public.before_message() returns trigger
language plpgsql security definer set search_path = public as $$
declare n integer; other uuid;
begin
  if auth.uid() is null then return new; end if;
  if exists (select 1 from public.profiles where id = auth.uid() and banned) then raise exception 'Your account has been suspended.'; end if;
  perform public.check_text(new.body);
  select count(*) into n from public.messages where sender_id = auth.uid() and created_at > now() - interval '1 minute';
  if n >= 20 then raise exception 'You''re sending messages too fast. Please slow down.'; end if;
  if not (select is_group from public.conversations where id = new.conversation_id) then
    select user_id into other from public.conversation_members where conversation_id = new.conversation_id and user_id <> auth.uid() limit 1;
    if other is not null and public.is_blocked(auth.uid(), other) then raise exception 'You can''t message this person.'; end if;
  end if;
  return new;
end $$;
drop trigger if exists messages_check on public.messages;
create trigger messages_check before insert on public.messages for each row execute function public.before_message();

create or replace function public.after_message() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  update public.conversations set last_message_at = new.created_at where id = new.conversation_id;
  update public.conversation_members set last_read_at = new.created_at where conversation_id = new.conversation_id and user_id = new.sender_id;
  return null;
end $$;
drop trigger if exists messages_after on public.messages;
create trigger messages_after after insert on public.messages for each row execute function public.after_message();

-- follows and reposts are checked too
create or replace function public.before_social() returns trigger
language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  if auth.uid() is null then return new; end if;
  if tg_table_name = 'follows' then
    if public.is_blocked(new.follower, new.followee) then raise exception 'You can''t follow this person.'; end if;
    select count(*) into n from public.follows where follower = auth.uid() and created_at > now() - interval '1 hour';
    if n >= 100 then raise exception 'Too many follows in one hour.'; end if;
  end if;
  return new;
end $$;
drop trigger if exists follows_check on public.follows;
create trigger follows_check before insert on public.follows for each row execute function public.before_social();

-- ---------------------------------------------------------------- notifications (quiet: no likes, only things that matter)
create table if not exists public.notifications (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles(id) on delete cascade,
  kind             text not null check (kind in ('reply','follow','repost','message','mention')),
  actor_id         uuid references public.profiles(id) on delete cascade,
  post_id          uuid references public.posts(id) on delete cascade,
  comment_id       uuid references public.comments(id) on delete cascade,
  conversation_id  uuid references public.conversations(id) on delete cascade,
  created_at       timestamptz not null default now(),
  read             boolean not null default false
);
create index if not exists notifications_user_idx on public.notifications (user_id, created_at desc);

create or replace function public.notify(target uuid, k text, actor uuid, pid uuid, cmid uuid, cid uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if target is null or target = actor or public.is_blocked(target, actor) then return; end if;
  -- one unread "message" alert per chat is enough
  if k = 'message' and exists (select 1 from public.notifications where user_id = target and kind = 'message' and conversation_id = cid and not read) then return; end if;
  insert into public.notifications (user_id, kind, actor_id, post_id, comment_id, conversation_id) values (target, k, actor, pid, cmid, cid);
end $$;

create or replace function public.make_notifications() returns trigger
language plpgsql security definer set search_path = public as $$
declare r record;
begin
  if tg_table_name = 'comments' then
    perform public.notify((select author_id from public.posts where id = new.post_id), 'reply', new.author_id, new.post_id, new.id, null);
    if new.parent_id is not null then
      perform public.notify((select author_id from public.comments where id = new.parent_id), 'reply', new.author_id, new.post_id, new.id, null);
    end if;
  elsif tg_table_name = 'follows' then
    perform public.notify(new.followee, 'follow', new.follower, null, null, null);
  elsif tg_table_name = 'reposts' then
    perform public.notify((select author_id from public.posts where id = new.post_id), 'repost', new.user_id, new.post_id, null, null);
  elsif tg_table_name = 'messages' then
    for r in select user_id from public.conversation_members where conversation_id = new.conversation_id and user_id <> new.sender_id and not muted loop
      perform public.notify(r.user_id, 'message', new.sender_id, null, null, new.conversation_id);
    end loop;
  end if;
  return null;
end $$;
drop trigger if exists comments_notify on public.comments;
create trigger comments_notify after insert on public.comments for each row execute function public.make_notifications();
drop trigger if exists follows_notify on public.follows;
create trigger follows_notify after insert on public.follows for each row execute function public.make_notifications();
drop trigger if exists reposts_notify on public.reposts;
create trigger reposts_notify after insert on public.reposts for each row execute function public.make_notifications();
drop trigger if exists messages_notify on public.messages;
create trigger messages_notify after insert on public.messages for each row execute function public.make_notifications();

-- reading a chat clears its message alert
create or replace function public.mark_chat_read(cid uuid) returns void
language sql security definer set search_path = public as $$
  update public.conversation_members set last_read_at = now() where conversation_id = cid and user_id = auth.uid();
  update public.notifications set read = true where user_id = auth.uid() and conversation_id = cid and not read;
$$;

-- ---------------------------------------------------------------- silent phone pop-ups (web push)
create schema if not exists private;
revoke all on schema private from public;
create table if not exists private.settings (key text primary key, value text not null);

create table if not exists public.push_subscriptions (
  endpoint    text primary key check (endpoint ~ '^https://'),
  user_id     uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  p256dh      text not null,
  auth        text not null,
  created_at  timestamptz not null default now()
);

do $$ begin
  create extension if not exists pg_net;
exception when others then raise notice 'pg_net not available here: phone pop-ups stay off.';
end $$;

-- every new notification asks the "push" function to pop it up on the person's phone
create or replace function public.send_push() returns trigger
language plpgsql security definer set search_path = public as $$
declare fn text; secret text;
begin
  select value into fn from private.settings where key = 'push_function_url';
  select value into secret from private.settings where key = 'push_secret';
  if fn is null or secret is null then return null; end if;
  if not exists (select 1 from public.push_subscriptions where user_id = new.user_id) then return null; end if;
  begin
    perform net.http_post(url := fn, body := jsonb_build_object('id', new.id),
                          headers := jsonb_build_object('Content-Type', 'application/json', 'x-push-secret', secret));
  exception when others then null;   -- a pop-up problem must never stop the site
  end;
  return null;
end $$;
drop trigger if exists notifications_push on public.notifications;
create trigger notifications_push after insert on public.notifications for each row execute function public.send_push();

-- the public half of the pop-up key, for the browser
create or replace function public.vapid_key() returns text
language sql stable security definer set search_path = public as $$
  select value from private.settings where key = 'vapid_public';
$$;

-- used only by the "push" function (with the secret) to build the pop-up
create or replace function public.push_job(nid uuid, secret text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare n record; who text; txt text; link text;
begin
  if secret is distinct from (select value from private.settings where key = 'push_secret') then raise exception 'denied'; end if;
  select * into n from public.notifications where id = nid;
  if n is null then return null; end if;
  select coalesce(display_name, username) into who from public.profiles where id = n.actor_id;
  txt := case n.kind
           when 'reply'   then who || ' replied to you'
           when 'follow'  then who || ' followed you'
           when 'repost'  then who || ' shared your post'
           when 'message' then 'New message from ' || who
           else who || ' mentioned you' end;
  link := case when n.conversation_id is not null then '#/chat/' || n.conversation_id
               when n.post_id is not null then '#/p/' || n.post_id
               else '#/u/' || (select username from public.profiles where id = n.actor_id) end;
  return jsonb_build_object(
    'title', 'Wire Now', 'body', txt, 'link', link,
    'vapid_public',  (select value from private.settings where key = 'vapid_public'),
    'vapid_private', (select value from private.settings where key = 'vapid_private'),
    'vapid_subject', (select value from private.settings where key = 'vapid_subject'),
    'subs', coalesce((select jsonb_agg(jsonb_build_object('endpoint', endpoint, 'keys', jsonb_build_object('p256dh', p256dh, 'auth', auth)))
                      from public.push_subscriptions where user_id = n.user_id), '[]'::jsonb));
end $$;

create or replace function public.push_gone(endpoint_url text, secret text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if secret is distinct from (select value from private.settings where key = 'push_secret') then raise exception 'denied'; end if;
  delete from public.push_subscriptions where endpoint = endpoint_url;
end $$;

-- ---------------------------------------------------------------- views for part 2
create or replace view public.feed with (security_invoker = true) as
select p.id, p.title, p.body, p.url, p.created_at, p.score, p.comment_count, p.removed,
       c.slug as community, c.name as community_name, c.is_official,
       pr.username as author, p.author_id,
       (p.score + 1) / power(extract(epoch from (now() - p.created_at)) / 3600 + 2, 1.5) as hot
from public.posts p
left join public.communities c on c.id = p.community_id
join public.profiles pr on pr.id = p.author_id
where not p.removed;

-- my chats with the latest message and whether there is something new
create or replace view public.my_chats with (security_invoker = true) as
select c.id, c.is_group, c.title, c.created_by, c.last_message_at, m.muted,
       (c.last_message_at > m.last_read_at) as unread,
       (select string_agg(coalesce(p.display_name, p.username), ', ' order by p.username)
          from public.conversation_members om join public.profiles p on p.id = om.user_id
         where om.conversation_id = c.id and om.user_id <> auth.uid()) as people,
       (select om.user_id from public.conversation_members om where om.conversation_id = c.id and om.user_id <> auth.uid() limit 1) as other_id,
       (select left(ms.body, 80) from public.messages ms where ms.conversation_id = c.id and not ms.removed order by ms.created_at desc limit 1) as last_text
from public.conversations c
join public.conversation_members m on m.conversation_id = c.id and m.user_id = auth.uid();

-- ---------------------------------------------------------------- rules for part 2
alter table public.follows              enable row level security;
alter table public.blocks               enable row level security;
alter table public.reposts              enable row level security;
alter table public.conversations        enable row level security;
alter table public.conversation_members enable row level security;
alter table public.messages             enable row level security;
alter table public.notifications        enable row level security;
alter table public.push_subscriptions   enable row level security;

drop policy if exists "create post" on public.posts;
create policy "create post" on public.posts for insert to authenticated with check (author_id = auth.uid() and not removed);

-- who follows whom is private to the two people involved (no public follower counts)
drop policy if exists "see own follows" on public.follows;
create policy "see own follows" on public.follows for select to authenticated using (follower = auth.uid() or followee = auth.uid());
drop policy if exists "follow" on public.follows;
create policy "follow" on public.follows for insert to authenticated with check (follower = auth.uid());
drop policy if exists "unfollow" on public.follows;
create policy "unfollow" on public.follows for delete to authenticated using (follower = auth.uid() or followee = auth.uid());

drop policy if exists "own blocks" on public.blocks;
create policy "own blocks" on public.blocks for all to authenticated using (blocker = auth.uid()) with check (blocker = auth.uid());

drop policy if exists "read reposts" on public.reposts;
create policy "read reposts" on public.reposts for select using (true);
drop policy if exists "own reposts" on public.reposts;
create policy "own reposts" on public.reposts for insert to authenticated with check (user_id = auth.uid());
drop policy if exists "undo repost" on public.reposts;
create policy "undo repost" on public.reposts for delete to authenticated using (user_id = auth.uid());

drop policy if exists "members see chat" on public.conversations;
create policy "members see chat" on public.conversations for select to authenticated using (public.is_member(id));
drop policy if exists "creator renames group" on public.conversations;
create policy "creator renames group" on public.conversations for update to authenticated using (created_by = auth.uid() and is_group);

drop policy if exists "members see members" on public.conversation_members;
create policy "members see members" on public.conversation_members for select to authenticated using (public.is_member(conversation_id));
drop policy if exists "update own membership" on public.conversation_members;
create policy "update own membership" on public.conversation_members for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "leave chat" on public.conversation_members;
create policy "leave chat" on public.conversation_members for delete to authenticated using (user_id = auth.uid());

drop policy if exists "members read messages" on public.messages;
create policy "members read messages" on public.messages for select to authenticated
  using ((public.is_member(conversation_id) and not removed)
         or (public.is_admin() and exists (select 1 from public.reports r where r.message_id = messages.id)));
drop policy if exists "members send messages" on public.messages;
create policy "members send messages" on public.messages for insert to authenticated with check (sender_id = auth.uid() and public.is_member(conversation_id));
drop policy if exists "delete own message" on public.messages;
create policy "delete own message" on public.messages for delete to authenticated using (sender_id = auth.uid());

drop policy if exists "own notifications" on public.notifications;
create policy "own notifications" on public.notifications for select to authenticated using (user_id = auth.uid());
drop policy if exists "mark own notifications" on public.notifications;
create policy "mark own notifications" on public.notifications for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "clear own notifications" on public.notifications;
create policy "clear own notifications" on public.notifications for delete to authenticated using (user_id = auth.uid());

drop policy if exists "own push" on public.push_subscriptions;
create policy "own push" on public.push_subscriptions for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- reporting a message also lets admins read just that message
drop policy if exists "send report" on public.reports;
create policy "send report" on public.reports for insert to authenticated
  with check (reporter = auth.uid() and (message_id is null or public.is_member((select conversation_id from public.messages where id = message_id))));

create or replace function public.moderate(kind text, target uuid, remove boolean default true) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can do this.'; end if;
  if kind = 'post' then update public.posts set removed = remove where id = target;
  elsif kind = 'comment' then update public.comments set removed = remove where id = target;
  elsif kind = 'message' then update public.messages set removed = remove where id = target;
  elsif kind = 'ban' then update public.profiles set banned = remove where id = target;
  elsif kind = 'report' then update public.reports set resolved = remove where id = target;
  else raise exception 'Unknown action'; end if;
end $$;

revoke all on public.follows, public.blocks, public.reposts, public.conversations, public.conversation_members,
              public.messages, public.notifications, public.push_subscriptions from anon, authenticated;
grant update (username, display_name, bio, dm_policy) on public.profiles to authenticated;
grant select on public.reposts to anon, authenticated;
grant select, delete on public.follows, public.blocks to authenticated;
grant insert (followee) on public.follows to authenticated;
grant insert (blocked) on public.blocks to authenticated;
grant insert (post_id), delete on public.reposts to authenticated;
grant select on public.conversations, public.conversation_members, public.my_chats, public.feed to authenticated;
grant select on public.feed to anon;
grant update (title) on public.conversations to authenticated;
grant update (last_read_at, muted), delete on public.conversation_members to authenticated;
grant select, delete on public.messages to authenticated;
grant insert (conversation_id, body) on public.messages to authenticated;
grant select, update (read), delete on public.notifications to authenticated;
grant select, insert, delete on public.push_subscriptions to authenticated;
grant insert (post_id, comment_id, message_id, reason) on public.reports to authenticated;

-- functions: only the ones meant for people can be called by them
revoke execute on all functions in schema public from public, anon, authenticated;
grant execute on function public.moderate(text, uuid, boolean), public.is_admin(), public.is_member(uuid),
  public.start_dm(uuid), public.create_group(text, uuid[]), public.add_to_group(uuid, uuid),
  public.mark_chat_read(uuid), public.vapid_key(), public.can_message(uuid, uuid), public.is_blocked(uuid, uuid) to authenticated;
grant execute on function public.vapid_key(), public.is_admin(), public.is_member(uuid) to anon;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    execute 'grant execute on function public.push_job(uuid, text), public.push_gone(text, text) to service_role';
  end if;
end $$;

-- live chat: new messages arrive instantly
do $$ begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
     and not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'messages') then
    execute 'alter publication supabase_realtime add table public.messages';
  end if;
end $$;

-- =====================================================================
-- PART 3: summaries written on request (double tap) and ahead of time
-- =====================================================================
create table if not exists public.summaries (
  story_id    text primary key check (char_length(story_id) <= 80),
  status      text not null default 'working' check (status in ('working','ready','failed')),
  cards       jsonb,
  title       text,
  link        text,
  source      text,
  reason      text,
  model       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists summaries_ready_idx on public.summaries (updated_at desc) where status = 'ready';

-- how often each story is opened: the most wanted stories are summarised first
create table if not exists public.story_demand (
  story_id  text primary key check (char_length(story_id) <= 80),
  opens     integer not null default 0,
  last_at   timestamptz not null default now()
);

create table if not exists public.ai_usage (day date primary key, used integer not null default 0);

-- only real story ids (10 hex characters) are counted, so nobody can fill the database with junk
create or replace function public.story_opened(sid text) returns void
language sql security definer set search_path = public as $$
  insert into public.story_demand (story_id, opens)
  select sid, 1 where sid ~ '^[0-9a-f]{10}$'
  on conflict (story_id) do update set opens = story_demand.opens + 1, last_at = now();
$$;

-- separate daily allowances for each helper (summaries / translations), so one can't use up the other
create table if not exists public.ai_usage_by (
  day date not null, kind text not null check (kind in ('summarize', 'translate')), used integer not null default 0,
  primary key (day, kind)
);
create or replace function public.ai_take_for(kind text, cap integer) returns boolean
language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  insert into public.ai_usage_by (day, kind, used) values (current_date, kind, 1)
  on conflict (day, kind) do update set used = ai_usage_by.used + 1 where ai_usage_by.used < cap
  returning used into n;
  return n is not null;
end $$;
alter table public.ai_usage_by enable row level security;
revoke all on public.ai_usage_by from anon, authenticated;
revoke execute on function public.ai_take_for(text, integer) from public, anon, authenticated;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    execute 'grant execute on function public.ai_take_for(text, integer) to service_role';
  end if;
end $$;

-- take one AI request from today's free allowance (false when it's used up)
create or replace function public.ai_take(cap integer) returns boolean
language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  insert into public.ai_usage (day, used) values (current_date, 1)
  on conflict (day) do update set used = ai_usage.used + 1 where ai_usage.used < cap
  returning used into n;
  return n is not null;
end $$;

alter table public.summaries    enable row level security;
alter table public.story_demand enable row level security;
alter table public.ai_usage     enable row level security;
drop policy if exists "read ready summaries" on public.summaries;
create policy "read ready summaries" on public.summaries for select using (status = 'ready');

revoke all on public.summaries, public.story_demand, public.ai_usage from anon, authenticated;
grant select (story_id, status, cards, source, updated_at) on public.summaries to anon, authenticated;
revoke execute on function public.story_opened(text), public.ai_take(integer) from public, anon, authenticated;
grant execute on function public.story_opened(text) to anon, authenticated;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    execute 'grant execute on function public.ai_take(integer) to service_role';
  end if;
end $$;

-- =====================================================================
-- PART 4: end-to-end encryption for private and group chats
-- The server only ever stores locked (encrypted) messages and locked keys.
-- Nobody with access to the database, the owner included, can read chats.
-- =====================================================================

-- each person's public key, and their private key locked with their chat password
create table if not exists public.user_keys (
  user_id          uuid primary key references public.profiles(id) on delete cascade default auth.uid(),
  public_key       jsonb not null,
  locked_private   text not null check (char_length(locked_private) <= 4000),
  salt             text not null check (char_length(salt) <= 100),
  iv               text not null check (char_length(iv) <= 100),
  created_at       timestamptz not null default now()
);
alter table public.user_keys add column if not exists recovery_private text check (char_length(recovery_private) <= 4000);
alter table public.user_keys add column if not exists recovery_salt text check (char_length(recovery_salt) <= 100);
alter table public.user_keys add column if not exists recovery_iv text check (char_length(recovery_iv) <= 100);

-- each chat has its own key, stored once per member, locked so only that member can open it
create table if not exists public.conversation_keys (
  conversation_id  uuid not null references public.conversations(id) on delete cascade,
  user_id          uuid not null references public.profiles(id) on delete cascade,
  wrapped_key      text not null check (char_length(wrapped_key) <= 400),
  wrapped_by       uuid not null references public.profiles(id) on delete cascade default auth.uid(),
  created_at       timestamptz not null default now(),
  primary key (conversation_id, user_id)
);

-- messages must be locked; plain text is refused by the database itself
alter table public.messages drop constraint if exists messages_body_check;
alter table public.messages add constraint messages_body_check check (body like 'e1:%' and char_length(body) between 10 and 12000);

-- a reporter can attach the unlocked text of the message they report
alter table public.reports add column if not exists message_text text check (char_length(message_text) <= 4000);

-- the word filter can't read locked messages any more; limits and blocks still apply
create or replace function public.before_message() returns trigger
language plpgsql security definer set search_path = public as $$
declare n integer; other uuid;
begin
  if auth.uid() is null then return new; end if;
  if exists (select 1 from public.profiles where id = auth.uid() and banned) then raise exception 'Your account has been suspended.'; end if;
  select count(*) into n from public.messages where sender_id = auth.uid() and created_at > now() - interval '1 minute';
  if n >= 20 then raise exception 'You''re sending messages too fast. Please slow down.'; end if;
  if not (select is_group from public.conversations where id = new.conversation_id) then
    select user_id into other from public.conversation_members where conversation_id = new.conversation_id and user_id <> auth.uid() limit 1;
    if other is not null and public.is_blocked(auth.uid(), other) then raise exception 'You can''t message this person.'; end if;
  end if;
  return new;
end $$;

-- you can only message people who have turned on private chats
create or replace function public.can_message(me uuid, other uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select me <> other
     and not public.is_blocked(me, other)
     and coalesce((select not banned from public.profiles where id = me), false)
     and exists (select 1 from public.user_keys where user_id = other)
     and case (select dm_policy from public.profiles where id = other)
           when 'everyone'  then true
           when 'following' then exists (select 1 from public.follows where follower = other and followee = me)
           else false end;
$$;

create or replace function public.start_dm(other uuid) returns uuid
language plpgsql security definer set search_path = public as $$
declare me uuid := auth.uid(); cid uuid;
begin
  if me is null then raise exception 'Please log in.'; end if;
  if not exists (select 1 from public.user_keys where user_id = me) then raise exception 'Turn on private chats first.'; end if;
  select c.id into cid from public.conversations c
    join public.conversation_members a on a.conversation_id = c.id and a.user_id = me
    join public.conversation_members b on b.conversation_id = c.id and b.user_id = other
   where not c.is_group limit 1;
  if cid is not null then
    if public.is_blocked(me, other) then raise exception 'You can''t message this person.'; end if;
    return cid;
  end if;
  if not exists (select 1 from public.user_keys where user_id = other) then
    raise exception 'This person hasn''t turned on private chats yet.';
  end if;
  if not public.can_message(me, other) then
    raise exception 'This person only accepts messages from people they follow.';
  end if;
  insert into public.conversations (is_group, created_by) values (false, me) returning id into cid;
  insert into public.conversation_members (conversation_id, user_id) values (cid, me), (cid, other);
  return cid;
end $$;

-- forgetting the chat password: start again with new keys (old messages can't be opened any more)
create or replace function public.reset_my_keys() returns void
language sql security definer set search_path = public as $$
  delete from public.conversation_keys where user_id = auth.uid();
  delete from public.user_keys where user_id = auth.uid();
$$;

alter table public.user_keys         enable row level security;
alter table public.conversation_keys enable row level security;

drop policy if exists "read public keys" on public.user_keys;
create policy "read public keys" on public.user_keys for select to authenticated using (true);
drop policy if exists "add own keys" on public.user_keys;
create policy "add own keys" on public.user_keys for insert to authenticated with check (user_id = auth.uid());
drop policy if exists "relock own keys" on public.user_keys;
create policy "relock own keys" on public.user_keys for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own chat keys" on public.conversation_keys;
create policy "own chat keys" on public.conversation_keys for select to authenticated using (user_id = auth.uid() or wrapped_by = auth.uid());
drop policy if exists "share chat keys" on public.conversation_keys;
create policy "share chat keys" on public.conversation_keys for insert to authenticated
  with check (wrapped_by = auth.uid() and public.is_member(conversation_id)
              and exists (select 1 from public.conversation_members m where m.conversation_id = conversation_keys.conversation_id and m.user_id = conversation_keys.user_id));

revoke all on public.user_keys, public.conversation_keys from anon, authenticated;
-- only the public half and the locked private half are readable; only the owner gets the locked half (column grant + view)
grant select (user_id, public_key) on public.user_keys to authenticated;
grant insert (public_key, locked_private, salt, iv, recovery_private, recovery_salt, recovery_iv) on public.user_keys to authenticated;
-- changing the password only re-locks the same key: the public key can't be swapped
grant update (locked_private, salt, iv, recovery_private, recovery_salt, recovery_iv) on public.user_keys to authenticated;
grant select, insert (conversation_id, user_id, wrapped_key) on public.conversation_keys to authenticated;
grant select on public.conversation_keys to authenticated;
grant insert (message_text) on public.reports to authenticated;

create or replace function public.my_locked_key() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object('public_key', public_key, 'locked_private', locked_private, 'salt', salt, 'iv', iv,
                            'recovery_private', recovery_private, 'recovery_salt', recovery_salt, 'recovery_iv', recovery_iv)
  from public.user_keys where user_id = auth.uid();
$$;

-- members who still need the chat key (new member, or someone who reset their password)
create or replace function public.members_missing_key(cid uuid) returns table (user_id uuid, public_key jsonb)
language sql stable security definer set search_path = public as $$
  select m.user_id, k.public_key from public.conversation_members m
  join public.user_keys k on k.user_id = m.user_id
  where m.conversation_id = cid and public.is_member(cid)
    and not exists (select 1 from public.conversation_keys ck where ck.conversation_id = cid and ck.user_id = m.user_id);
$$;

revoke execute on function public.my_locked_key(), public.members_missing_key(uuid), public.reset_my_keys() from public, anon;
grant execute on function public.my_locked_key(), public.members_missing_key(uuid), public.reset_my_keys(),
  public.start_dm(uuid), public.can_message(uuid, uuid) to authenticated;

-- chat list previews: the full locked text of the last message (the phone unlocks and shortens it)
create or replace view public.my_chats with (security_invoker = true) as
select c.id, c.is_group, c.title, c.created_by, c.last_message_at, m.muted,
       (c.last_message_at > m.last_read_at) as unread,
       (select string_agg(coalesce(p.display_name, p.username), ', ' order by p.username)
          from public.conversation_members om join public.profiles p on p.id = om.user_id
         where om.conversation_id = c.id and om.user_id <> auth.uid()) as people,
       (select om.user_id from public.conversation_members om where om.conversation_id = c.id and om.user_id <> auth.uid() limit 1) as other_id,
       (select ms.body from public.messages ms where ms.conversation_id = c.id and not ms.removed order by ms.created_at desc limit 1) as last_text
from public.conversations c
join public.conversation_members m on m.conversation_id = c.id and m.user_id = auth.uid();

-- =====================================================================
-- PART 5: authenticator app (6-digit codes) for logging in
-- Anyone can add one. Once added, private things need the code.
-- Admin powers always need it.
-- =====================================================================
create or replace function public.mfa_ok() returns boolean
language sql stable security definer set search_path = public as $$
  select auth.uid() is null
      or coalesce(auth.jwt() ->> 'aal', 'aal1') = 'aal2'
      or not exists (select 1 from auth.mfa_factors f where f.user_id = auth.uid() and f.status = 'verified');
$$;

-- admins only count as admins after entering their authenticator code
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select is_admin from public.profiles where id = auth.uid()), false)
     and coalesce(auth.jwt() ->> 'aal', 'aal1') = 'aal2';
$$;

-- if someone has an authenticator, their private things stay shut until they enter the code
do $$
declare t text;
begin
  foreach t in array array['messages','conversation_keys','user_keys','conversations','conversation_members',
                           'notifications','push_subscriptions','follows','blocks','reports','post_votes','comment_votes'] loop
    execute format('drop policy if exists "authenticator" on public.%I', t);
    execute format('create policy "authenticator" on public.%I as restrictive for all to authenticated using (public.mfa_ok()) with check (public.mfa_ok())', t);
  end loop;
  foreach t in array array['posts','comments','reposts','communities','profiles'] loop
    execute format('drop policy if exists "authenticator ins" on public.%I', t);
    execute format('create policy "authenticator ins" on public.%I as restrictive for insert to authenticated with check (public.mfa_ok())', t);
    execute format('drop policy if exists "authenticator upd" on public.%I', t);
    execute format('create policy "authenticator upd" on public.%I as restrictive for update to authenticated using (public.mfa_ok())', t);
    execute format('drop policy if exists "authenticator del" on public.%I', t);
    execute format('create policy "authenticator del" on public.%I as restrictive for delete to authenticated using (public.mfa_ok())', t);
  end loop;
end $$;

-- the chat-key helpers check it too
create or replace function public.my_locked_key() returns jsonb
language sql stable security definer set search_path = public as $$
  select case when public.mfa_ok() then
    (select jsonb_build_object('public_key', public_key, 'locked_private', locked_private, 'salt', salt, 'iv', iv,
                               'recovery_private', recovery_private, 'recovery_salt', recovery_salt, 'recovery_iv', recovery_iv)
       from public.user_keys where user_id = auth.uid()) end;
$$;

revoke execute on function public.mfa_ok() from public, anon;
grant execute on function public.mfa_ok() to authenticated;
grant execute on function public.is_admin() to anon, authenticated;

-- =====================================================================
-- PART 6: translations into any language (done once, shared by everyone)
-- =====================================================================
create table if not exists public.translations (
  key         text not null check (char_length(key) <= 64),     -- fingerprint of the English text
  lang        text not null check (lang ~ '^[a-z]{2,3}(-[A-Za-z]{2,4})?$'),
  text        text not null check (char_length(text) <= 8000),
  created_at  timestamptz not null default now(),
  primary key (key, lang)
);
create index if not exists translations_lang_idx on public.translations (lang, created_at desc);

-- which languages people pick (counts only, nothing about who): the Meaning Engine trains the most-used first
create table if not exists public.language_use (
  lang   text primary key check (lang ~ '^[a-z]{2,3}(-[A-Za-z]{2,4})?$'),
  picks  integer not null default 0
);
-- the languages Wire Now can translate properly (the same list as the website and the translator)
create or replace function public.supported_lang(l text) returns boolean
language sql immutable as $$
  select l = any (array['en','si','ta','hi','bn','te','mr','ur','gu','kn','ml','pa','ne','ar','he','fa','tr','ru','uk','pl',
    'de','fr','es','pt','it','nl','ro','el','sv','no','da','fi','hu','cs','sk','sr','hr','bg','zh','ja','ko','vi','th','id',
    'ms','tl','sw']);
$$;
create or replace function public.language_picked(l text) returns void
language sql security definer set search_path = public as $$
  insert into public.language_use (lang, picks) select l, 1 where public.supported_lang(l)
  on conflict (lang) do update set picks = language_use.picks + 1;
$$;

-- translations that failed the checks: not asked again for a day (saves the free allowance)
create table if not exists public.translation_fails (
  key text not null, lang text not null, at timestamptz not null default now(), primary key (key, lang)
);
alter table public.translation_fails enable row level security;
revoke all on public.translation_fails from anon, authenticated;

alter table public.translations enable row level security;
alter table public.language_use enable row level security;
drop policy if exists "read translations" on public.translations;
create policy "read translations" on public.translations for select using (true);
revoke all on public.translations, public.language_use from anon, authenticated;
grant select on public.translations to anon, authenticated;
revoke execute on function public.language_picked(text) from public;
grant execute on function public.language_picked(text) to anon, authenticated;

-- =====================================================================
-- PART 7: the Wire Now Fact Base (our own facts about the world) and "Is this true?"
-- Facts come from Wire Now's checked summaries; each keeps WHO reported it and WHEN.
-- "confirmed" needs 2 or more independent outlets. Only the robot (through the "facts" helper) writes.
-- =====================================================================
create table if not exists public.facts (
  key          text primary key check (char_length(key) <= 64),       -- fingerprint of story + statement
  story_id     text not null check (char_length(story_id) <= 20),
  statement    text not null check (char_length(statement) <= 600),
  topic        text check (char_length(topic) <= 40),
  country      text check (char_length(country) <= 60),
  place        text check (char_length(place) <= 120),
  sources      text[] not null default '{}',
  source_count integer not null default 1,
  link         text check (char_length(link) <= 600),
  reported_at  timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  search       tsvector generated always as (to_tsvector('simple', coalesce(statement, '') || ' ' || coalesce(place, '') || ' ' || coalesce(country, ''))) stored
);
create index if not exists facts_search_idx on public.facts using gin (search);
create index if not exists facts_story_idx on public.facts (story_id);
create index if not exists facts_time_idx on public.facts (reported_at desc);

create table if not exists public.people (
  name        text primary key check (char_length(name) <= 120),     -- lower-case name
  display     text not null check (char_length(display) <= 120),
  role        text check (char_length(role) <= 120),
  country     text check (char_length(country) <= 60),
  mentions    integer not null default 1,
  stories     text[] not null default '{}',
  last_seen   timestamptz not null default now()
);

create table if not exists public.claim_checks (
  key          text primary key check (char_length(key) <= 64),       -- fingerprint of the claim (+ language)
  claim        text not null check (char_length(claim) <= 600),
  lang         text not null default 'en',
  verdict      text not null check (verdict in ('confirmed', 'false', 'misleading', 'unverified')),
  explanation  text not null check (char_length(explanation) <= 2000),
  sources      jsonb not null default '[]',
  asked        integer not null default 1,
  created_at   timestamptz not null default now()
);
create index if not exists claim_checks_popular_idx on public.claim_checks (asked desc, created_at desc);

-- the daily allowance now also covers "Is this true?" checks
alter table public.ai_usage_by drop constraint if exists ai_usage_by_kind_check;
alter table public.ai_usage_by add constraint ai_usage_by_kind_check check (kind in ('summarize', 'translate', 'check'));

alter table public.facts        enable row level security;
alter table public.people       enable row level security;
alter table public.claim_checks enable row level security;
drop policy if exists "read facts" on public.facts;
create policy "read facts" on public.facts for select using (true);
drop policy if exists "read people" on public.people;
create policy "read people" on public.people for select using (true);
drop policy if exists "read checks" on public.claim_checks;
create policy "read checks" on public.claim_checks for select using (true);
revoke all on public.facts, public.people, public.claim_checks from anon, authenticated;
grant select on public.facts, public.people to anon, authenticated;
grant select (key, claim, lang, verdict, explanation, sources, asked, created_at) on public.claim_checks to anon, authenticated;
