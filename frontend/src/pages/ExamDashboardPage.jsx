import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { bootstrapExamCourse, getExamMaterials, getExamOverview } from '../lib/api';


const PROCESSING_LABELS = {
  text: ['可检索', 'text-emerald-800 bg-emerald-100/70'],
  ocr: ['待 OCR', 'text-amber-900 bg-amber-100/80'],
  convert: ['待转换', 'text-rose-900 bg-rose-100/80'],
};

function StudyTrack({ track, index }) {
  return (
    <article className="atlas-track">
      <div className="atlas-track__number">卷{index === 0 ? '甲' : '乙'}</div>
      <div>
        <p className="atlas-kicker">{track.points} 分 · {track.required ? '必修路线' : '选修路线'}</p>
        <h3>{track.name}</h3>
        <p>{index === 0 ? '学科基础、人文地理、自然地理、历史地图与GIS' : '史前至清亡，按时代组织史实与论证'}</p>
      </div>
    </article>
  );
}

function MaterialRow({ item }) {
  const [label, style] = PROCESSING_LABELS[item.processing];
  return (
    <li className="material-row">
      <span className={`material-dot ${item.available ? 'is-ready' : ''}`} aria-hidden="true" />
      <span className="material-name" title={item.path}>{item.filename}</span>
      <span className="material-role">{item.role}</span>
      <span className={`material-status ${style}`}>{label}</span>
    </li>
  );
}

export default function ExamDashboardPage() {
  const [overview, setOverview] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    Promise.all([getExamOverview(), getExamMaterials()])
      .then(([exam, library]) => {
        if (cancelled) return;
        setOverview(exam);
        setMaterials(library.items);
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => { cancelled = true; };
  }, []);

  async function startStudy() {
    if (overview?.course_id) {
      navigate(`/course/${overview.course_id}`);
      return;
    }
    setStarting(true);
    setError('');
    try {
      const course = await bootstrapExamCourse();
      navigate(`/course/${course.course_id}`);
    } catch (err) {
      setError(err.message);
      setStarting(false);
    }
  }

  if (!overview && !error) {
    return <div className="atlas-loading">正在展开备考地图…</div>;
  }

  return (
    <div className="atlas-shell">
      <header className="atlas-header">
        <a className="atlas-brand" href="/" aria-label="返回备考台">
          <span className="atlas-seal">禹贡</span>
          <span><strong>历史地理备考台</strong><small>FUDAN · 2027</small></span>
        </a>
        <nav>
          <button onClick={() => navigate('/courses')}>全部课程</button>
          <button onClick={() => navigate('/profile')}>学习记录</button>
        </nav>
      </header>

      <main className="atlas-main">
        {error && <p className="atlas-error">{error}</p>}

        <section className="atlas-hero">
          <div className="atlas-coordinate">31°18′N · 121°30′E</div>
          <div className="atlas-hero__copy">
            <p className="atlas-kicker">当前阶段 · 基础建图</p>
            <h1>把庞杂史地知识，<br />收束成一张能作答的地图。</h1>
            <p className="atlas-lead">目标不是“看完资料”，而是在考场上准确调取史实、材料与论证结构。</p>
            <div className="atlas-actions">
              <button className="atlas-primary" onClick={startStudy} disabled={starting}>
                {starting ? '正在建立课程…' : overview?.course_id ? '继续今日学习' : '从诊断课开始'}
              </button>
              <a className="atlas-secondary" href="/api/exam/anki.tsv">导出首批 Anki 卡片</a>
            </div>
          </div>
          <div className="atlas-countdown" aria-label={`距离参考考试日还有${overview?.days_remaining}天`}>
            <span className="atlas-countdown__ring" />
            <strong>{overview?.days_remaining}</strong>
            <span>天</span>
            <small>至12月底参考考试日</small>
          </div>
        </section>

        <section className="atlas-section">
          <div className="atlas-section__heading">
            <div><p className="atlas-kicker">考试结构</p><h2>双卷轴 · 300分</h2></div>
            <p>中国历史路线已锁定。2027目录发布后复核科目代码与具体结构。</p>
          </div>
          <div className="atlas-tracks">
            {overview?.tracks.map((track, index) => <StudyTrack key={track.name} track={track} index={index} />)}
          </div>
        </section>

        <section className="atlas-grid">
          <article className="atlas-panel atlas-today">
            <div className="atlas-section__heading compact">
              <div><p className="atlas-kicker">今日闭环</p><h2>先输出，再订正</h2></div>
              <span className="atlas-date">DAY 001</span>
            </div>
            <ol>
              {overview?.today.map((task, index) => (
                <li key={task}><span>{String(index + 1).padStart(2, '0')}</span><p>{task}</p></li>
              ))}
            </ol>
            <p className="atlas-note">完成标准：留下可检查的答案、卡片或订正记录，而不是只读一遍。</p>
          </article>

          <article className="atlas-panel atlas-library">
            <div className="atlas-section__heading compact">
              <div><p className="atlas-kicker">核心资料库</p><h2>{overview?.material_ready}/{overview?.material_count} 份已定位</h2></div>
              <span className="atlas-date">{overview?.ocr_pending} 份待 OCR</span>
            </div>
            <ul>{materials.map((item) => <MaterialRow key={item.filename} item={item} />)}</ul>
          </article>
        </section>

        <footer className="atlas-footer">
          <p>资料事实以原文件为准；网络检索只用于补缺与交叉核验。</p>
          <p>基线：复旦历史地理研究中心 2024-10-16 考试大纲</p>
        </footer>
      </main>
    </div>
  );
}
