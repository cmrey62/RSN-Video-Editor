"""
 @file
 @brief This file can easily query Clips, Files, and other project data
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import os
import copy

from classes import info
from classes.app import get_app
from classes.logger import log
import openshot


class QueryObject:
    """ This class allows one or more project data objects to be queried """

    def __init__(self):
        """ Constructor """

        self.id = None  # Unique ID of object
        self.key = None  # Key path to object in project data
        self.data = None  # Data dictionary of object
        self.parent = None  # Only used with effects (who belong to clips)
        self.type = "insert"  # Type of operation needed to save

    def save(self, OBJECT_TYPE):
        """ Save the object back to the project data store """

        # Insert or Update this data into the project data store
        if not self.id and self.type == "insert":

            # Insert record, and Generate id
            self.id = get_app().project.generate_id()

            # save id in data (if attribute found)
            self.data["id"] = copy.deepcopy(self.id)

            # Set key (if needed)
            if not self.key:
                self.key = copy.deepcopy(OBJECT_TYPE.object_key)
                self.key.append({"id": self.id})

            # Insert into project data
            get_app().updates.insert(copy.deepcopy(OBJECT_TYPE.object_key), copy.deepcopy(self.data))

            # Mark record as 'update' now... so another call to this method won't insert it again
            self.type = "update"

        elif self.id and self.type == "update":

            # Update existing project data
            get_app().updates.update(self.key, self.data)

    def delete(self, OBJECT_TYPE):
        """ Delete the object from the project data store """

        # Delete if object found and not pending insert
        if self.id and self.type == "update":
            # Delete from project data store
            get_app().updates.delete(self.key)
            self.type = "delete"

    def title(self):
        """ Get the translated display title of this item """
        # Needs to be overwritten in each derived class
        return None

    def filter(OBJECT_TYPE, **kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """

        # Get a list of all objects of this type
        parent = get_app().project.get(OBJECT_TYPE.object_key)

        if not parent:
            return []

        matching_objects = []

        # Loop through all children objects
        for child in parent:

            # Protect against non-iterable/subscriptables
            if not child:
                continue

            # Loop through all kwargs (and look for matches)
            match = True
            for key, value in kwargs.items():

                if key in child and child[key] != value:
                    match = False
                    break

                # Intersection Position
                if key == "intersect" and (
                    child.get("position", 0) > value
                    or child.get("position", 0) + (child.get("end", 0) - child.get("start", 0)) < value
                ):
                    match = False


            # Add matched record
            if match:
                object = OBJECT_TYPE()
                object.id = child["id"]
                object.key = [OBJECT_TYPE.object_name, {"id": object.id}]
                object.data = copy.deepcopy(child)  # copy of object
                object.type = "update"
                matching_objects.append(object)

        # Return matching objects
        return matching_objects

    def get(OBJECT_TYPE, **kwargs):
        """ Take any arguments given as filters, and find the first matching object """

        # Look for matching objects
        matching_objects = QueryObject.filter(OBJECT_TYPE, **kwargs)

        if matching_objects:
            return matching_objects[0]
        else:
            return None


class Clip(QueryObject):
    """ This class allows Clips to be queried, updated, and deleted from the project data. """
    object_name = "clips"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Clip)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Clip)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Clip, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Clip, **kwargs)

    def title(self):
        """ Get the translated display title of this item """
        path = self.data.get("reader", {}).get("path")
        return os.path.basename(path)

    def showAudioData(self):
        
        if "ui" not in self.data:
            self.data["ui"] = {}
            self.save()

        # Get File
        file_path = self.data.get("reader").get("path")
        file = File.get(path = file_path)
        # Get File's audio data
        file_audio_data = file.data.get("ui",{}).get("audio_data", False)
        if not file_audio_data:
            log.info("clip.showAudioData was called, but file has no audio data")
            return

        sample_count = len(file_audio_data)
        file_duration = file.data.get("duration")
        time_per_sample = file_duration / sample_count
        def sample_from_time(time):
            sample_num = max(0, round(time / time_per_sample))
            sample_num = min(sample_count - 1, sample_num)
            return file_audio_data[sample_num]

        audio_data = []
        # clip = Clip.get(id = self.data.get("id"))
        clip = get_app().window.timeline_sync.timeline.GetClip(self.data.get("id"))
        num_frames = int(self.data.get("reader").get("video_length"))
        fps = get_app().project.get("fps")
        fps_frac = fps["num"] / fps["den"]
        for frame_num in range(1, num_frames):
            print(f"Clipshow: frame {frame_num}")
            volume = clip.volume.GetValue(frame_num)
            display_frame =  clip.time.GetValue(frame_num)
            time = display_frame / fps_frac
            audio_data.append(sample_from_time(time) * volume)

        self.data["ui"]["audio_data"] = audio_data
        self.save()
        return

    def removeAudioData(self):
        pass

class Transition(QueryObject):
    """ This class allows Transitions (i.e. timeline effects) to be queried, updated, and deleted from the project data. """
    object_name = "effects"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Transition)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Transition)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Transition, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Transition, **kwargs)

    def title(self):
        """ Get the translated display title of this item """
        path = self.data.get("reader", {}).get("path")
        fileBaseName = os.path.splitext(os.path.basename(path))[0]

        # split the name into parts (looking for a number)
        suffix_number = None
        name_parts = fileBaseName.split("_")
        if name_parts[-1].isdigit():
            suffix_number = name_parts[-1]
        # get name of transition
        item_name = fileBaseName.replace("_", " ").capitalize()

        # replace suffix number with placeholder (if any)
        if suffix_number:
            item_name = item_name.replace(suffix_number, "%s")
            item_name = get_app()._tr(item_name) % suffix_number
        else:
            item_name = get_app()._tr(item_name)
        return item_name


class File(QueryObject):
    """ This class allows Files to be queried, updated, and deleted from the project data. """
    object_name = "files"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(File)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(File)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(File, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(File, **kwargs)

    def absolute_path(self):
        """ Get absolute file path of file """

        file_path = self.data["path"]
        if os.path.isabs(file_path):
            return file_path

        # Try to expand path relative to project folder
        app = get_app()
        if (app and hasattr("project", app)
           and hasattr("current_filepath", app.project)):
            project_folder = os.path.dirname(app.project.current_filepath)
            file_path = os.path.abspath(os.path.join(project_folder, file_path))

        return file_path

    def relative_path(self):
        """ Get relative path (based on the current working directory) """

        file_path = self.absolute_path()
        # Convert path to relative (based on current working directory of Python)
        return os.path.relpath(file_path, info.CWD)

    def getAudioData(self):
        # Ensure that UI attribute exists
        if "ui" not in self.data:
            self.data["ui"] = {}
            self.save()

        audio_data = self.data["ui"].get("audio_data", False)
        if audio_data and len(audio_data) > 1:
            log.info("Audio Data already retrieved.")
            return
        if not audio_data:
            # Placeholder value. Communicates that data is being retrieved
            self.data["ui"]["audio_data"] = [-999]

        # Do the audio data stuff.
        temp_clip = openshot.Clip(self.data["path"])
        temp_clip.Open()
        temp_clip.Reader().info.has_video = False

        sample_rate = temp_clip.Reader().info.sample_rate
        samples_per_second = 20
        sample_divisor = round(sample_rate / samples_per_second)

        audio_data = []
        for frame_num in range(1, temp_clip.Reader().info.video_length):
            print(f"FileShow: frame {frame_num}")
            frame = temp_clip.Reader().GetFrame(frame_num)

            sample_num = 0
            max_samples = frame.GetAudioSamplesCount()
            while sample_num < max_samples:
                magnitude_range = sample_divisor
                if sample_num + magnitude_range > frame.GetAudioSamplesCount():
                    magnitude_range = frame.GetAudioSamplesCount() - sample_num
                sample_value = frame.GetAudioSample(-1, sample_num, magnitude_range)
                audio_data.append(sample_value)

                sample_num += sample_divisor
        self.data["ui"]["audio_data"] = audio_data
        self.save()
        return


class Marker(QueryObject):
    """ This class allows Markers to be queried, updated, and deleted from the project data. """
    object_name = "markers"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Marker)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Marker)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Marker, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Marker, **kwargs)


class Track(QueryObject):
    """ This class allows Tracks to be queried, updated, and deleted from the project data. """
    object_name = "layers"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Track)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Track)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Track, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Track, **kwargs)

    def __lt__(self, other):
        return self.data.get('number', 0) < other.data.get('number', 0)

    def __gt__(self, other):
        return self.data.get('number', 0) > other.data.get('number', 0)


class Effect(QueryObject):
    """ This class allows Effects to be queried, updated, and deleted from the project data. """
    object_name = "effects"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Effect)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Effect)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """

        # Get a list of clips
        clips = get_app().project.get("clips")
        matching_objects = []

        # Loop through all clips
        if clips:
            for clip in clips:
                # Loop through all effects
                if "effects" in clip:
                    for child in clip["effects"]:

                        # Loop through all kwargs (and look for matches)
                        match = True
                        for key, value in kwargs.items():
                            if key in child and child[key] != value:
                                match = False
                                break

                        # Add matched record
                        if match:
                            object = Effect()
                            object.id = child["id"]
                            object.key = ["clips", {"id": clip["id"]}, "effects", {"id": object.id}]
                            object.data = child
                            object.type = "update"
                            object.parent = clip
                            matching_objects.append(object)

        # Return matching objects
        return matching_objects

    def title(self):
        """ Get the translated display title of this item """
        return self.data.get("name") or self.data.get("type")

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        # Look for matching objects
        matching_objects = Effect.filter(**kwargs)

        if matching_objects:
            return matching_objects[0]
        else:
            return None
