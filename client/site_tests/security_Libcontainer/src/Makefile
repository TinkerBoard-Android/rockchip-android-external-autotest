# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PKG_CONFIG ?= pkg-config
BASE_VER = $(shell cat $(SYSROOT)/usr/share/libchrome/BASE_VER)
DEP_LIBS = libchrome libcontainer libminijail
CXXFLAGS += $(shell $(PKG_CONFIG) --cflags $(DEP_LIBS))
CXXFLAGS += -std=gnu++14 -Werror -Wall
LDFLAGS += $(shell $(PKG_CONFIG) --libs $(DEP_LIBS))
LDFLAGS += -lgtest

TARGET_UNITTEST = libcontainer_target_test

all: $(TARGET_UNITTEST)

$(TARGET_UNITTEST): libcontainer_target_unittest.cc
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -g -o $@ $^ $(LDFLAGS)

.PHONY: clean
clean:
	$(RM) $(TARGET_UNITTEST)
