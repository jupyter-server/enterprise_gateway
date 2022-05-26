/*
 * Copyright (c) Jupyter Development Team.
 * Distributed under the terms of the Modified BSD License.
 */

name := "toree-launcher"

version := sys.props.getOrElse("version", default = "1.0").replaceAll("dev[0-9]", "SNAPSHOT")

scalaVersion := "2.12.12"

resolvers += "Typesafe Repo" at "https://repo.typesafe.com/typesafe/releases/"
/* resolvers += "Sonatype Repository" at "https://oss.sonatype.org/content/repositories/releases/" */
resolvers += "Sonatype Maven Central Mirror" at "https://maven-central.storage-download.googleapis.com/maven2/"

libraryDependencies += "com.typesafe.play" %% "play-json" % "2.7.4" // Apache v2
libraryDependencies += "org.apache.toree" % "toree-assembly" % "0.5.0-incubating" from "https://repository.apache.org/content/repositories/orgapachetoree-1020/org/apache/toree/toree-assembly/0.5.0-incubating/toree-assembly-0.5.0-incubating.jar"
