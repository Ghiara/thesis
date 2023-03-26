# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from mtrl.utils.types import TensorType


@dataclass
class ReplayBufferSample:
    __slots__ = [
        "env_obs",
        "action",
        "reward",
        "next_env_obs",
        "not_done",
        "task_obs",
        # "true_label",
        # "one_hot",
        "buffer_index",
    ]
    env_obs: TensorType
    action: TensorType
    reward: TensorType
    next_env_obs: TensorType
    not_done: TensorType
    task_obs: TensorType
    # Add true label to indicate which env it comes from
    # true_label: TensorType
    # one_hot: TensorType
    buffer_index: TensorType


class ReplayBuffer(object):
    """Buffer to store environment transitions."""

    def __init__(
        self, env_obs_shape, task_obs_shape, action_shape, capacity, batch_size, device
    ):
        self.env_obs_shape = env_obs_shape
        self.task_obs_shape = task_obs_shape
        self.action_shape = action_shape
        self.capacity = capacity
        self.batch_size = batch_size
        self.device = device

        # the proprioceptive env_obs is stored as float32, pixels env_obs as uint8
        self.env_obs_dtype = np.float32 if len(env_obs_shape) == 1 else np.uint8
        self.task_obs_dtype = np.int64

        self.env_obses = np.empty((capacity, *env_obs_shape), dtype=self.env_obs_dtype)
        self.next_env_obses = np.empty((capacity, *env_obs_shape), dtype=self.env_obs_dtype)
        self.actions = np.empty((capacity, *action_shape), dtype=np.float32)
        self.rewards = np.empty((capacity, 1), dtype=np.float32)
        self.not_dones = np.empty((capacity, 1), dtype=np.float32)
        self.task_obs = np.empty((capacity, *task_obs_shape), dtype=self.task_obs_dtype)
        # TODO add true labels
        # self.true_labels = np.empty((capacity, 1), dtype=np.float32)
        # self.one_hot = np.empty((capacity, *(10,)), dtype=np.int64)
        
        self.idx = 0
        self.last_save = 0
        self.full = False

    def reset_buffer(self):
        self.env_obses = np.empty((self.capacity, *self.env_obs_shape), dtype=self.env_obs_dtype)
        self.next_env_obses = np.empty((self.capacity, *self.env_obs_shape), dtype=self.env_obs_dtype)
        self.actions = np.empty((self.capacity, *self.action_shape), dtype=np.float32)
        self.rewards = np.empty((self.capacity, 1), dtype=np.float32)
        self.not_dones = np.empty((self.capacity, 1), dtype=np.float32)
        self.task_obs = np.empty((self.capacity, *self.task_obs_shape), dtype=self.task_obs_dtype)
        # add true labels
        # self.true_labels = np.empty((self.capacity, 1), dtype=np.float32)
        # self.one_hot = np.empty((self.capacity, *(10,)), dtype=np.int64)

        self.idx = 0
        self.last_save = 0
        self.full = False


    def is_empty(self):
        return self.idx == 0

    def add(self, env_obs, action, reward, next_env_obs, done, task_obs):
        '''
        Inputs: obs, acts, rews, dones from single environment
        # TODO true label
        '''
        np.copyto(self.env_obses[self.idx], env_obs)
        np.copyto(self.actions[self.idx], action)
        np.copyto(self.rewards[self.idx], reward)
        np.copyto(self.next_env_obses[self.idx], next_env_obs)
        np.copyto(self.not_dones[self.idx], not done)
        np.copyto(self.task_obs[self.idx], task_obs)
        # add true labels
        # np.copyto(self.true_labels[self.idx], true_label)
        # np.copyto(self.one_hot[self.idx], one_hot)

        self.idx = (self.idx + 1) % self.capacity
        self.full = self.full or self.idx == 0

    def sample(self, index=None) -> ReplayBufferSample:
        if index is None:
            idxs = np.random.randint(
                0, self.capacity if self.full else self.idx, size=self.batch_size
            )
        else:
            idxs = index

        env_obses = torch.as_tensor(self.env_obses[idxs], device=self.device).float()
        actions = torch.as_tensor(self.actions[idxs], device=self.device)
        rewards = torch.as_tensor(self.rewards[idxs], device=self.device)
        next_env_obses = torch.as_tensor(self.next_env_obses[idxs], device=self.device).float()
        not_dones = torch.as_tensor(self.not_dones[idxs], device=self.device)
        env_indices = torch.as_tensor(self.task_obs[idxs], device=self.device)
        # add true labels
        # true_labels = torch.as_tensor(self.true_labels[idxs], device=self.device)
        # one_hot = torch.as_tensor(self.one_hot[idxs], device=self.device)
        return ReplayBufferSample(
            env_obses, actions, rewards, next_env_obses, not_dones, env_indices, idxs
        )

    def sample_an_index(
        self, index, total_number_of_environments
    ) -> ReplayBufferSample:
        """Return env_observations for only the given index"""
        idxs = np.random.randint(
            0,
            self.capacity if self.full else self.idx,
            size=total_number_of_environments * self.batch_size * 4,
        )

        idxs = np.asarray(
            [_idx for _idx in idxs if int(self.task_obs[_idx][0]) == index][
                : self.batch_size
            ]
        )

        env_obses = torch.as_tensor(self.env_obses[idxs], device=self.device).float()
        actions = torch.as_tensor(self.actions[idxs], device=self.device)
        rewards = torch.as_tensor(self.rewards[idxs], device=self.device)
        next_env_obses = torch.as_tensor(self.next_env_obses[idxs], device=self.device).float()
        not_dones = torch.as_tensor(self.not_dones[idxs], device=self.device)
        env_indices = torch.as_tensor(self.task_obs[idxs], device=self.device)
        # add true labels
        # true_labels = torch.as_tensor(self.true_labels[idxs], device=self.device)
        # one_hot = torch.as_tensor(self.one_hot[idxs], device=self.device)
        return ReplayBufferSample(
            env_obses, actions, rewards, next_env_obses, not_dones, env_indices, idxs
        )

    def _sample_a_replay_buffer(self, num_samples):
        """This method returns a new replay buffer which contains samples from the original replay buffer.
        For now, this is meant to be used only when saving a replay buffer.
        """
        indices = np.random.choice(
            self.capacity if self.full else self.idx, num_samples, replace=False
        )
        # we can revisit this later, if needed
        new_replay_buffer = ReplayBuffer(
            env_obs_shape=self.env_obses.shape[1:],
            action_shape=self.actions.shape[1:],
            capacity=num_samples,
            batch_size=self.batch_size,
            device=self.device,
        )
        new_replay_buffer.env_obses = self.env_obses[indices]
        new_replay_buffer.next_env_obses = self.next_env_obses[indices]
        new_replay_buffer.actions = self.actions[indices]
        new_replay_buffer.rewards = self.rewards[indices]
        new_replay_buffer.not_dones = self.not_dones[indices]
        new_replay_buffer.task_obs = self.task_obs[indices]
        # add a true label
        # new_replay_buffer.true_labels = self.true_labels[indices]
        # new_replay_buffer.one_hot = self.one_hot[indices]

        return new_replay_buffer

    def delete_from_filesystem(self, dir_to_delete_from: str):
        for filename in os.listdir(dir_to_delete_from):
            file_path = os.path.join(dir_to_delete_from, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                print(f"Deleted {file_path}")
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")
        print(f"Deleted files from: {dir_to_delete_from}")

    def save(self, save_dir, size_per_chunk: int, num_samples_to_save: int):
        if self.idx == self.last_save:
            return
        if num_samples_to_save == -1:
            # Save the entire replay buffer
            self._save_all(
                save_dir=save_dir,
                size_per_chunk=size_per_chunk,
            )
        else:
            if num_samples_to_save > self.idx:
                num_samples_to_save = self.idx
                replay_buffer_to_save = self
            else:
                replay_buffer_to_save = self._sample_a_replay_buffer(
                    num_samples=num_samples_to_save
                )
                replay_buffer_to_save.idx = num_samples_to_save
                replay_buffer_to_save.last_save = 0
            backup_dir_path = Path(f"{save_dir}_bk")
            if not backup_dir_path.exists():
                backup_dir_path.mkdir()
            replay_buffer_to_save._save_all(
                save_dir=str(backup_dir_path),
                size_per_chunk=size_per_chunk,
            )
            replay_buffer_to_save.delete_from_filesystem(dir_to_delete_from=save_dir)
            backup_dir_path.rename(save_dir)
        self.last_save = self.idx

    def _save_all(self, save_dir, size_per_chunk: int):
        if self.idx == self.last_save:
            return
        if self.last_save == self.capacity:
            self.last_save = 0
        if self.idx > self.last_save:
            self._save_payload(
                save_dir=save_dir,
                start_idx=self.last_save,
                end_idx=self.idx,
                size_per_chunk=size_per_chunk,
            )
        else:
            self._save_payload(
                save_dir=save_dir,
                start_idx=self.last_save,
                end_idx=self.capacity,
                size_per_chunk=size_per_chunk,
            )
            self._save_payload(
                save_dir=save_dir,
                start_idx=0,
                end_idx=self.idx,
                size_per_chunk=size_per_chunk,
            )
        self.last_save = self.idx

    def _save_payload(
        self, save_dir: str, start_idx: int, end_idx: int, size_per_chunk: int
    ):
        while True:
            if size_per_chunk > 0:
                current_end_idx = min(start_idx + size_per_chunk, end_idx)
            else:
                current_end_idx = end_idx
            self._save_payload_chunk(
                save_dir=save_dir, start_idx=start_idx, end_idx=current_end_idx
            )
            if current_end_idx == end_idx:
                break
            start_idx = current_end_idx

    def _save_payload_chunk(self, save_dir: str, start_idx: int, end_idx: int):
        path = os.path.join(save_dir, f"{start_idx}_{end_idx-1}.pt")
        payload = [
            self.env_obses[start_idx:end_idx],
            self.next_env_obses[start_idx:end_idx],
            self.actions[start_idx:end_idx],
            self.rewards[start_idx:end_idx],
            self.not_dones[start_idx:end_idx],
            self.task_obs[start_idx:end_idx],
            # add a true label --> payload[6]
            # self.true_labels[start_idx:end_idx]
            # self.one_hot[start_idx:end_idx],
        ]
        print(f"Saving replay buffer at {path}")
        torch.save(payload, path)

    def load(self, save_dir):
        chunks = os.listdir(save_dir)
        chunks = sorted(chunks, key=lambda x: int(x.split("_")[0]))
        start = 0
        for chunk in chunks:
            path = os.path.join(save_dir, chunk)
            try:
                payload = torch.load(path)
                end = start + payload[0].shape[0]
                if end > self.capacity:
                    # this condition is added for resuming some very old experiments.
                    # This condition should not be needed with the new experiments
                    # and should be removed going forward.
                    select_till_index = payload[0].shape[0] - (end - self.capacity)
                    end = start + select_till_index
                else:
                    select_till_index = payload[0].shape[0]
                self.env_obses[start:end] = payload[0][:select_till_index]
                self.next_env_obses[start:end] = payload[1][:select_till_index]
                self.actions[start:end] = payload[2][:select_till_index]
                self.rewards[start:end] = payload[3][:select_till_index]
                self.not_dones[start:end] = payload[4][:select_till_index]
                self.task_obs[start:end] = payload[5][:select_till_index]
                # add a true label
                # self.true_labels[start:end] = payload[6][:select_till_index]
                # self.one_hot[start:end] = payload[6][:select_till_index]
                
                self.idx = end - 1
                start = end
                print(f"Loaded replay buffer from path: {path})")
            except EOFError as e:
                print(
                    f"Skipping loading replay buffer from path: {path} due to error: {e}"
                )
        self.last_save = self.idx
        # self.delete_from_filesystem(dir_to_delete_from=save_dir)

    def reset(self):
        self.idx = 0