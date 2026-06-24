import React from 'react';
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

const yellow = '#ffd21f';
const cyan = '#32d6ff';
const violet = '#8b5cf6';
const white = '#fff';

const fit = (frame, from, duration = 18) =>
  interpolate(frame, [from, from + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

const GridBackground = () => {
  const frame = useCurrentFrame();
  const x = interpolate(frame, [0, 300], [0, -48], {
    extrapolateRight: 'extend',
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#050505',
        backgroundImage: `
          linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px),
          linear-gradient(rgba(255,210,31,.12) 2px, transparent 2px),
          linear-gradient(90deg, rgba(255,210,31,.12) 2px, transparent 2px),
          radial-gradient(circle at 75% 20%, rgba(255,210,31,.15), transparent 26%),
          radial-gradient(circle at 18% 78%, rgba(50,214,255,.11), transparent 22%)
        `,
        backgroundSize: '48px 48px,48px 48px,240px 240px,240px 240px,auto,auto',
        backgroundPosition: `${x}px 0, ${x}px 0, 0 0, 0 0, center, center`,
      }}
    >
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,.35) 60%, rgba(0,0,0,.76) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};

const Brand = ({repo}) => (
  <div
    style={{
      position: 'absolute',
      top: 48,
      left: 72,
      display: 'flex',
      alignItems: 'center',
      gap: 18,
      zIndex: 20,
    }}
  >
    <div
      style={{
        width: 58,
        height: 58,
        borderRadius: 8,
        background: yellow,
        color: '#000',
        display: 'grid',
        placeItems: 'center',
        fontWeight: 900,
        fontSize: 30,
      }}
    >
      GH
    </div>
    <div style={{fontSize: 30, color: '#b8b8b8', fontWeight: 800}}>
      开源项目拆解 <span style={{color: yellow}}>{repo}</span>
    </div>
  </div>
);

const MetricPanel = ({active}) => {
  const rows = [
    ['粉丝', '468.9万'],
    ['获赞', '2091.6万'],
    ['作品', '600'],
    ['同步', '20条新作品'],
  ];
  return (
    <div
      style={{
        position: 'absolute',
        right: 72,
        top: 210,
        width: 520,
        padding: 22,
        borderRadius: 8,
        background: 'linear-gradient(145deg, rgba(18,18,18,.96), rgba(35,35,35,.92))',
        border: '1px solid rgba(255,255,255,.15)',
        boxShadow: '0 26px 80px rgba(0,0,0,.45)',
        transform: `translateY(${(1 - active) * 36}px)`,
        opacity: active,
      }}
    >
      <div style={{display: 'flex', gap: 12, marginBottom: 18}}>
        <div style={{width: 54, height: 54, borderRadius: '50%', background: yellow}} />
        <div>
          <div style={{fontSize: 30, fontWeight: 900}}>对标账号</div>
          <div style={{fontSize: 20, color: '#aaa'}}>自动同步账号和作品数据</div>
        </div>
      </div>
      {rows.map((row, index) => (
        <div
          key={row[0]}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            padding: '14px 0',
            borderTop: '1px solid rgba(255,255,255,.1)',
            fontSize: 28,
            transform: `translateX(${(1 - active) * (30 + index * 10)}px)`,
          }}
        >
          <span style={{color: '#aaa'}}>{row[0]}</span>
          <strong style={{color: index === 3 ? cyan : white}}>{row[1]}</strong>
        </div>
      ))}
    </div>
  );
};

const Flow = ({items, progress}) => (
  <div
    style={{
      position: 'absolute',
      left: 72,
      right: 72,
      bottom: 76,
      display: 'grid',
      gridTemplateColumns: `repeat(${items.length}, 1fr)`,
      gap: 14,
    }}
  >
    {items.map((item, index) => {
      const lit = progress * items.length > index;
      return (
        <div
          key={item}
          style={{
            height: 104,
            borderRadius: 8,
            border: `1px solid ${lit ? yellow : 'rgba(255,255,255,.13)'}`,
            background: lit ? 'rgba(255,210,31,.94)' : 'rgba(255,255,255,.055)',
            color: lit ? '#000' : '#cfcfcf',
            display: 'grid',
            placeItems: 'center',
            fontSize: 28,
            fontWeight: 900,
          }}
        >
          {item}
        </div>
      );
    })}
  </div>
);

const Scene = ({scene, index, start, end}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const appear = fit(frame, start, 18);
  const leave = interpolate(frame, [end - 12, end], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = appear * leave;
  const scale = spring({
    fps,
    frame: Math.max(0, frame - start),
    config: {damping: 18, stiffness: 90},
  });
  const chipAppear = (i) => fit(frame, start + 22 + i * 5, 12);
  return (
    <AbsoluteFill
      style={{
        padding: '170px 72px 180px',
        opacity,
        transform: `translateY(${(1 - appear) * 34}px) scale(${0.985 + scale * 0.015})`,
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          height: 58,
          padding: '0 28px',
          borderRadius: 8,
          background: yellow,
          color: '#000',
          fontSize: 32,
          fontWeight: 900,
        }}
      >
        {String(index + 1).padStart(2, '0')} / {scene.label}
      </div>
      <h1
        style={{
          maxWidth: 1180,
          margin: '36px 0 0',
          fontSize: 96,
          lineHeight: 1.08,
          letterSpacing: 0,
          fontWeight: 900,
          color: white,
        }}
      >
        {scene.headline}
        <br />
        <span style={{color: yellow}}>{scene.accent}</span>
      </h1>
      <div
        style={{
          marginTop: 34,
          maxWidth: 1040,
          color: '#d8d8d8',
          fontSize: 38,
          lineHeight: 1.45,
          fontWeight: 700,
        }}
      >
        {scene.body}
      </div>
      <div style={{display: 'flex', gap: 16, marginTop: 38, flexWrap: 'wrap', maxWidth: 1060}}>
        {scene.chips.map((chip, i) => (
          <div
            key={chip}
            style={{
              opacity: chipAppear(i),
              transform: `translateY(${(1 - chipAppear(i)) * 16}px)`,
              padding: '14px 22px',
              borderRadius: 8,
              background: i === 0 ? cyan : i === 1 ? violet : 'rgba(255,255,255,.12)',
              color: i < 2 ? '#000' : white,
              fontSize: 28,
              fontWeight: 900,
            }}
          >
            {chip}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Subtitle = ({text, start, end}) => {
  const frame = useCurrentFrame();
  const opacity =
    fit(frame, start, 8) *
    interpolate(frame, [end - 8, end], [1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  return (
    <div
      style={{
        position: 'absolute',
        left: 250,
        right: 250,
        bottom: 28,
        minHeight: 72,
        display: 'grid',
        placeItems: 'center',
        opacity,
        color: white,
        fontSize: 34,
        fontWeight: 900,
        lineHeight: 1.25,
        textAlign: 'center',
        textShadow: '0 4px 0 #000, 0 0 18px #000',
      }}
    >
      {text}
    </div>
  );
};

export const ProjectVideo = ({data}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const sceneLength = Math.floor(durationInFrames / data.scenes.length);
  const progress = frame / durationInFrames;
  const activeScene = Math.min(data.scenes.length - 1, Math.floor(frame / sceneLength));
  const subtitleIndex = Math.min(data.narration.length - 1, Math.floor(frame / (durationInFrames / data.narration.length)));
  const subtitleStart = Math.floor(subtitleIndex * (durationInFrames / data.narration.length));
  const subtitleEnd = Math.floor((subtitleIndex + 1) * (durationInFrames / data.narration.length));

  return (
    <AbsoluteFill style={{fontFamily: '"Microsoft YaHei", "SimHei", sans-serif', background: '#050505'}}>
      <GridBackground />
      <Brand repo={data.repo} />
      {data.scenes.map((scene, index) => (
        <Scene
          key={scene.label}
          scene={scene}
          index={index}
          start={index * sceneLength}
          end={index === data.scenes.length - 1 ? durationInFrames : (index + 1) * sceneLength}
        />
      ))}
      <MetricPanel active={activeScene >= 1 && activeScene <= 3 ? 1 : 0.32} />
      <Flow items={data.flow} progress={progress} />
      <Subtitle text={data.narration[subtitleIndex]} start={subtitleStart} end={subtitleEnd} />
      <div
        style={{
          position: 'absolute',
          left: 0,
          bottom: 0,
          width: `${progress * 100}%`,
          height: 8,
          background: yellow,
        }}
      />
      <Audio src={staticFile('narration.wav')} />
    </AbsoluteFill>
  );
};
