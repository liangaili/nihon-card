(async () => {
  const tokenMatch = location.href.match(/token=(\d+)/);
  const token = tokenMatch ? tokenMatch[1] : "1297516062";
  const all = [];
  const seen = new Set();
  let begin = 0;
  const count = 20;
  let totalCount = null;

  while (true) {
    const u = "/cgi-bin/appmsgpublish?sub=list&begin=" + begin + "&count=" + count +
              "&token=" + token + "&lang=zh_CN&f=json&ajax=1";
    const resp = await fetch(u, { credentials: "include" });
    const raw = await resp.text();
    let data;
    try { data = JSON.parse(raw); } catch (e) {
      return JSON.stringify({ error: "JSON parse failed at begin=" + begin, snippet: raw.slice(0, 300) });
    }
    if (!data.publish_page) {
      return JSON.stringify({ error: "no publish_page", begin: begin, resp: raw.slice(0, 300) });
    }
    const page = JSON.parse(data.publish_page);
    if (totalCount === null) totalCount = page.total_count;
    const list = page.publish_list || [];
    for (const item of list) {
      let info;
      try { info = JSON.parse(item.publish_info); } catch (e) { continue; }
      const sendTime = (info.sent_info && info.sent_info.time) || 0;
      const appmsgs = info.appmsg_info || [];
      for (const a of appmsgs) {
        if (!a.content_url) continue;
        const key = a.content_url;
        if (seen.has(key)) continue;
        seen.add(key);
        all.push({
          title: a.title || "",
          url: a.content_url,
          cover: a.cover || "",
          timestamp: sendTime,
          date: sendTime ? new Date(sendTime * 1000).toISOString().slice(0, 10) : "",
          itemidx: a.itemidx || 1,
          appmsgid: a.appmsgid || 0,
          read_num: a.read_num || 0
        });
      }
    }
    begin += count;
    if (list.length < count || all.length >= totalCount) break;
    if (begin > 2000) break;
  }

  // 按发布时间从旧到新排序，便于成书顺序
  all.sort((x, y) => (x.timestamp - y.timestamp) || (x.itemidx - y.itemidx));
  return JSON.stringify({ totalCount: totalCount, fetched: all.length, articles: all });
})()
