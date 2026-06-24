import React from 'react';
import {Composition} from 'remotion';
import {ProjectVideo} from './ProjectVideo.jsx';
import {videoData} from './data.js';

export const RemotionRoot = () => {
  return (
    <Composition
      id="ProjectVideo"
      component={ProjectVideo}
      durationInFrames={videoData.durationInFrames}
      fps={videoData.fps}
      width={1920}
      height={1080}
      defaultProps={{
        data: videoData,
      }}
    />
  );
};
